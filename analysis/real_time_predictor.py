import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger
import threading
import time
import queue
from collections import deque
import asyncio
from dataclasses import dataclass

@dataclass
class PredictionResult:
    """预测结果数据类"""
    timestamp: datetime
    symbol: str
    prediction: str
    confidence: float
    features: Dict[str, float]
    model_type: str

class RealTimePredictor:
    """实时预测器
    
    提供流式数据处理和实时预测功能
    """
    
    def __init__(self, model_dir: str = "models", buffer_size: int = 1000):
        """
        初始化实时预测器
        
        Args:
            model_dir: 模型文件目录
            buffer_size: 数据缓冲区大小
        """
        self.model_dir = model_dir
        self.buffer_size = buffer_size
        
        # 数据缓冲区
        self.data_buffer = deque(maxlen=buffer_size)
        self.prediction_queue = queue.Queue()
        
        # 模型相关
        self.models = {}
        self.scalers = {}
        self.label_encoders = {}
        self.feature_columns = []
        
        # 控制变量
        self.is_running = False
        self.prediction_thread = None
        self.processing_interval = 1.0  # 处理间隔（秒）
        
        # 性能统计
        self.stats = {
            'total_predictions': 0,
            'successful_predictions': 0,
            'failed_predictions': 0,
            'avg_processing_time': 0.0,
            'last_prediction_time': None
        }
        
        logger.info(f"实时预测器初始化完成，缓冲区大小: {buffer_size}")
    
    def load_models(self, model_type: str = 'ensemble') -> bool:
        """
        加载预训练模型
        
        Args:
            model_type: 模型类型 ('ensemble', 'single')
            
        Returns:
            是否加载成功
        """
        try:
            logger.info(f"加载模型，类型: {model_type}")
            
            if model_type == 'ensemble':
                # 加载集成模型
                ensemble_path = os.path.join(self.model_dir, 'ensemble_models.pkl')
                if os.path.exists(ensemble_path):
                    ensemble_data = joblib.load(ensemble_path)
                    self.models = ensemble_data['models']
                    self.scalers['ensemble'] = ensemble_data['scaler']
                    self.label_encoders['ensemble'] = ensemble_data['label_encoder']
                    self.feature_columns = ensemble_data['feature_columns']
                    logger.info(f"集成模型加载成功，包含 {len(self.models)} 个子模型")
                    return True
                else:
                    logger.error("集成模型文件不存在")
                    return False
            
            elif model_type == 'single':
                # 加载单个模型
                model_files = {
                    'rf': 'random_forest_model.pkl',
                    'gb': 'gradient_boosting_model.pkl',
                    'xgb': 'xgboost_model.pkl',
                    'lgb': 'lightgbm_model.pkl'
                }
                
                loaded_count = 0
                for name, filename in model_files.items():
                    model_path = os.path.join(self.model_dir, filename)
                    if os.path.exists(model_path):
                        model_data = joblib.load(model_path)
                        self.models[name] = model_data['model']
                        self.scalers[name] = model_data['scaler']
                        self.label_encoders[name] = model_data['label_encoder']
                        if not self.feature_columns:
                            self.feature_columns = model_data.get('feature_columns', [])
                        loaded_count += 1
                
                if loaded_count > 0:
                    logger.info(f"单个模型加载成功，共 {loaded_count} 个模型")
                    return True
                else:
                    logger.error("没有找到可用的单个模型文件")
                    return False
            
            else:
                logger.error(f"不支持的模型类型: {model_type}")
                return False
                
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False
    
    def add_data_point(self, data: Dict[str, Any]) -> bool:
        """
        添加新的数据点到缓冲区
        
        Args:
            data: 数据点，包含时间戳和特征值
            
        Returns:
            是否添加成功
        """
        try:
            # 添加时间戳
            if 'timestamp' not in data:
                data['timestamp'] = datetime.now()
            
            # 验证数据格式
            if not isinstance(data, dict):
                logger.error("数据格式错误，必须是字典类型")
                return False
            
            # 添加到缓冲区
            self.data_buffer.append(data)
            
            # 如果缓冲区满了，触发预测
            if len(self.data_buffer) >= self.buffer_size * 0.8:  # 80%满时触发
                self._trigger_prediction()
            
            return True
            
        except Exception as e:
            logger.error(f"添加数据点失败: {e}")
            return False
    
    def add_batch_data(self, data_list: List[Dict[str, Any]]) -> int:
        """
        批量添加数据点
        
        Args:
            data_list: 数据点列表
            
        Returns:
            成功添加的数据点数量
        """
        success_count = 0
        for data in data_list:
            if self.add_data_point(data):
                success_count += 1
        
        logger.info(f"批量添加数据完成，成功: {success_count}/{len(data_list)}")
        return success_count
    
    def _prepare_features(self, data_points: List[Dict[str, Any]]) -> Optional[pd.DataFrame]:
        """
        准备特征数据
        
        Args:
            data_points: 数据点列表
            
        Returns:
            特征DataFrame或None
        """
        try:
            if not data_points:
                return None
            
            # 转换为DataFrame
            df = pd.DataFrame(data_points)
            
            # 确保包含所需特征
            for col in self.feature_columns:
                if col not in df.columns:
                    df[col] = 0.0  # 缺失特征用0填充
            
            # 选择特征列并保持顺序
            df = df[self.feature_columns]
            
            # 处理分类特征
            categorical_features = ['hour_of_day', 'day_of_week', 'day_of_month']
            for feature in categorical_features:
                if feature in df.columns:
                    df[feature] = df[feature].astype('category')
            
            return df
            
        except Exception as e:
            logger.error(f"准备特征数据失败: {e}")
            return None
    
    def _predict_batch(self, X: pd.DataFrame, model_name: str = 'best') -> List[PredictionResult]:
        """
        批量预测
        
        Args:
            X: 特征数据
            model_name: 模型名称
            
        Returns:
            预测结果列表
        """
        results = []
        
        try:
            start_time = time.time()
            
            # 选择模型和预处理器
            if model_name == 'best' and 'soft_voting' in self.models:
                model = self.models['soft_voting']
                scaler = self.scalers.get('ensemble')
                label_encoder = self.label_encoders.get('ensemble')
            elif model_name in self.models:
                model = self.models[model_name]
                scaler = self.scalers.get(model_name) or self.scalers.get('ensemble')
                label_encoder = self.label_encoders.get(model_name) or self.label_encoders.get('ensemble')
            else:
                # 使用第一个可用模型
                model_name = list(self.models.keys())[0]
                model = self.models[model_name]
                scaler = self.scalers.get(model_name) or self.scalers.get('ensemble')
                label_encoder = self.label_encoders.get(model_name) or self.label_encoders.get('ensemble')
            
            if not all([model, scaler, label_encoder]):
                logger.error("模型、缩放器或标签编码器缺失")
                return results
            
            # 数据预处理
            X_scaled = scaler.transform(X)
            X_scaled = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
            
            # 预测
            predictions_encoded = model.predict(X_scaled)
            predictions_proba = None
            
            try:
                predictions_proba = model.predict_proba(X_scaled)
            except:
                pass
            
            # 解码预测结果
            predictions = label_encoder.inverse_transform(predictions_encoded)
            
            # 生成结果
            for i, (pred, pred_encoded) in enumerate(zip(predictions, predictions_encoded)):
                confidence = 0.5  # 默认置信度
                if predictions_proba is not None:
                    confidence = float(np.max(predictions_proba[i]))
                
                result = PredictionResult(
                    timestamp=datetime.now(),
                    symbol='UNKNOWN',  # 需要从输入数据中获取
                    prediction=str(pred),
                    confidence=confidence,
                    features=X.iloc[i].to_dict(),
                    model_type=model_name
                )
                results.append(result)
            
            # 更新统计信息
            processing_time = time.time() - start_time
            self.stats['total_predictions'] += len(results)
            self.stats['successful_predictions'] += len(results)
            self.stats['avg_processing_time'] = (
                self.stats['avg_processing_time'] * 0.9 + processing_time * 0.1
            )
            self.stats['last_prediction_time'] = datetime.now()
            
            logger.info(f"批量预测完成，样本数: {len(results)}, 耗时: {processing_time:.3f}s")
            
        except Exception as e:
            logger.error(f"批量预测失败: {e}")
            self.stats['failed_predictions'] += len(X) if not X.empty else 1
        
        return results
    
    def _trigger_prediction(self):
        """
        触发预测处理
        """
        if not self.data_buffer:
            return
        
        # 获取缓冲区数据
        data_points = list(self.data_buffer)
        self.data_buffer.clear()
        
        # 准备特征
        X = self._prepare_features(data_points)
        if X is None or X.empty:
            logger.warning("特征准备失败，跳过预测")
            return
        
        # 执行预测
        predictions = self._predict_batch(X)
        
        # 将结果放入队列
        for pred in predictions:
            self.prediction_queue.put(pred)
    
    def _prediction_worker(self):
        """
        预测工作线程
        """
        logger.info("预测工作线程启动")
        
        while self.is_running:
            try:
                # 定期检查缓冲区
                if len(self.data_buffer) > 0:
                    self._trigger_prediction()
                
                time.sleep(self.processing_interval)
                
            except Exception as e:
                logger.error(f"预测工作线程错误: {e}")
                time.sleep(1)
        
        logger.info("预测工作线程停止")
    
    def start_real_time_prediction(self, processing_interval: float = 1.0) -> bool:
        """
        启动实时预测
        
        Args:
            processing_interval: 处理间隔（秒）
            
        Returns:
            是否启动成功
        """
        try:
            if self.is_running:
                logger.warning("实时预测已在运行")
                return True
            
            if not self.models:
                logger.error("没有加载模型，无法启动实时预测")
                return False
            
            self.processing_interval = processing_interval
            self.is_running = True
            
            # 启动预测线程
            self.prediction_thread = threading.Thread(
                target=self._prediction_worker,
                daemon=True
            )
            self.prediction_thread.start()
            
            logger.info(f"实时预测启动成功，处理间隔: {processing_interval}s")
            return True
            
        except Exception as e:
            logger.error(f"启动实时预测失败: {e}")
            return False
    
    def stop_real_time_prediction(self):
        """
        停止实时预测
        """
        if not self.is_running:
            logger.warning("实时预测未在运行")
            return
        
        logger.info("停止实时预测...")
        self.is_running = False
        
        if self.prediction_thread and self.prediction_thread.is_alive():
            self.prediction_thread.join(timeout=5)
        
        logger.info("实时预测已停止")
    
    def get_latest_predictions(self, count: int = 10) -> List[PredictionResult]:
        """
        获取最新的预测结果
        
        Args:
            count: 获取数量
            
        Returns:
            预测结果列表
        """
        results = []
        
        try:
            for _ in range(min(count, self.prediction_queue.qsize())):
                if not self.prediction_queue.empty():
                    results.append(self.prediction_queue.get_nowait())
        except queue.Empty:
            pass
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取预测统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.stats.copy()
        stats.update({
            'is_running': self.is_running,
            'buffer_size': len(self.data_buffer),
            'queue_size': self.prediction_queue.qsize(),
            'loaded_models': list(self.models.keys()),
            'feature_count': len(self.feature_columns)
        })
        
        return stats
    
    def predict_single(self, data: Dict[str, Any], model_name: str = 'best') -> Optional[PredictionResult]:
        """
        单次预测
        
        Args:
            data: 输入数据
            model_name: 模型名称
            
        Returns:
            预测结果或None
        """
        try:
            # 准备数据
            df = pd.DataFrame([data])
            X = self._prepare_features([data])
            
            if X is None or X.empty:
                logger.error("特征准备失败")
                return None
            
            # 执行预测
            results = self._predict_batch(X, model_name)
            
            return results[0] if results else None
            
        except Exception as e:
            logger.error(f"单次预测失败: {e}")
            return None
    
    def __del__(self):
        """析构函数"""
        self.stop_real_time_prediction()