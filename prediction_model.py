import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import joblib
import os
from database import TradingDatabase
from enhanced_indicators import EnhancedTechnicalIndicators

class TradingPredictionModel:
    """交易预测模型"""
    
    def __init__(self, db_path: str = "trading_data.db", model_dir: str = "models"):
        self.db = TradingDatabase(db_path)
        self.model_dir = model_dir
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.rf_model = None
        self.gb_model = None
        self.feature_columns = []
        self.model_trained = False
        
        # 创建模型目录
        os.makedirs(model_dir, exist_ok=True)
        
        # 尝试加载已有模型，如果失败则初始化新模型
        if not self.load_models():
            logger.info("未找到已训练模型，将在首次预测时自动训练")
            self._initialize_default_model()
    
    def _initialize_default_model(self):
        """初始化默认模型参数"""
        self.feature_columns = [
            'rsi_14', 'macd', 'macd_signal', 'bb_width', 'kdj_k', 'kdj_d',
            'williams_r', 'cci', 'atr_percent', 'volume_ratio', 'volatility',
            'adx', 'aroon_up', 'aroon_down', 'stoch_k', 'stoch_d'
        ]
        # 训练一个基础模型
        X, y = self.prepare_training_data(30)  # 使用较少天数的模拟数据
        if not X.empty and not y.empty:
            self.train_models(X, y)
            self.save_models()
    
    def prepare_training_data(self, days: int = 90) -> Tuple[pd.DataFrame, pd.Series]:
        """准备训练数据"""
        try:
            logger.info(f"准备 {days} 天的训练数据")
            
            # 获取历史分析结果和对应的价格数据
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            
            # 这里需要从数据库获取历史数据
            # 暂时创建模拟数据用于演示
            training_data = self._create_mock_training_data()
            
            if training_data.empty:
                logger.warning("没有足够的训练数据")
                return pd.DataFrame(), pd.Series()
            
            # 分离特征和标签
            feature_columns = [col for col in training_data.columns if col not in ['outcome', 'symbol', 'timestamp']]
            X = training_data[feature_columns]
            y = training_data['outcome']
            
            self.feature_columns = feature_columns
            
            logger.info(f"准备了 {len(X)} 条训练样本，{len(feature_columns)} 个特征")
            return X, y
            
        except Exception as e:
            logger.error(f"准备训练数据失败: {e}")
            return pd.DataFrame(), pd.Series()
    
    def _create_mock_training_data(self) -> pd.DataFrame:
        """创建模拟训练数据（实际应用中应从数据库获取）"""
        np.random.seed(42)
        n_samples = 1000
        
        data = {
            # 技术指标特征
            'rsi_14': np.random.uniform(20, 80, n_samples),
            'macd': np.random.uniform(-0.5, 0.5, n_samples),
            'macd_signal': np.random.uniform(-0.5, 0.5, n_samples),
            'bb_width': np.random.uniform(1, 10, n_samples),
            'kdj_k': np.random.uniform(0, 100, n_samples),
            'kdj_d': np.random.uniform(0, 100, n_samples),
            'williams_r': np.random.uniform(-100, 0, n_samples),
            'cci': np.random.uniform(-200, 200, n_samples),
            'atr_percent': np.random.uniform(0.5, 5, n_samples),
            'volume_ratio': np.random.uniform(0.5, 3, n_samples),
            'volatility': np.random.uniform(0.1, 2, n_samples),
            'adx': np.random.uniform(10, 50, n_samples),
            
            # 价格相关特征
            'price_change_1h': np.random.uniform(-5, 5, n_samples),
            'price_change_4h': np.random.uniform(-10, 10, n_samples),
            'price_change_24h': np.random.uniform(-20, 20, n_samples),
            
            # 市场特征
            'market_cap_rank': np.random.randint(1, 100, n_samples),
            'trading_volume_24h': np.random.uniform(1e6, 1e9, n_samples),
            
            # 信心度和风险等级
            'confidence': np.random.uniform(0.3, 0.95, n_samples),
            'risk_level': np.random.choice(['low', 'medium', 'high'], n_samples),
            
            # 时间特征
            'hour_of_day': np.random.randint(0, 24, n_samples),
            'day_of_week': np.random.randint(0, 7, n_samples),
        }
        
        df = pd.DataFrame(data)
        
        # 创建目标变量（基于一些规则）
        outcomes = []
        for _, row in df.iterrows():
            # 简单的规则：RSI超卖且MACD金叉且高信心度 -> 更可能成功
            score = 0
            
            if row['rsi_14'] < 30:  # RSI超卖
                score += 1
            if row['rsi_14'] > 70:  # RSI超买（做空信号）
                score += 1
            if row['macd'] > row['macd_signal']:  # MACD金叉
                score += 1
            if row['confidence'] > 0.7:  # 高信心度
                score += 2
            if row['volatility'] < 1:  # 低波动率
                score += 1
            if row['volume_ratio'] > 1.5:  # 高成交量
                score += 1
            
            # 添加随机性
            score += np.random.normal(0, 1)
            
            # 转换为二分类结果
            outcome = 'win' if score > 3 else 'loss'
            outcomes.append(outcome)
        
        df['outcome'] = outcomes
        df['symbol'] = np.random.choice(['BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'BNB-USDT-SWAP'], n_samples)
        df['timestamp'] = pd.date_range(start='2024-01-01', periods=n_samples, freq='1H')
        
        return df
    
    def train_models(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """训练预测模型"""
        try:
            if X.empty or y.empty:
                logger.error("训练数据为空")
                return {}
            
            logger.info("开始训练预测模型")
            
            # 处理分类特征
            X_processed = X.copy()
            categorical_columns = ['risk_level']
            
            for col in categorical_columns:
                if col in X_processed.columns:
                    X_processed[col] = self.label_encoder.fit_transform(X_processed[col].astype(str))
            
            # 标准化特征
            X_scaled = self.scaler.fit_transform(X_processed)
            X_scaled = pd.DataFrame(X_scaled, columns=X_processed.columns)
            
            # 编码目标变量
            y_encoded = self.label_encoder.fit_transform(y)
            
            # 分割训练和测试数据
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
            )
            
            # 训练随机森林模型
            logger.info("训练随机森林模型")
            self.rf_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1
            )
            self.rf_model.fit(X_train, y_train)
            
            # 训练梯度提升模型
            logger.info("训练梯度提升模型")
            self.gb_model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42
            )
            self.gb_model.fit(X_train, y_train)
            
            # 评估模型
            rf_pred = self.rf_model.predict(X_test)
            gb_pred = self.gb_model.predict(X_test)
            
            # 计算评估指标
            rf_metrics = {
                'rf_accuracy': accuracy_score(y_test, rf_pred),
                'rf_precision': precision_score(y_test, rf_pred, average='weighted'),
                'rf_recall': recall_score(y_test, rf_pred, average='weighted'),
                'rf_f1': f1_score(y_test, rf_pred, average='weighted')
            }
            
            gb_metrics = {
                'gb_accuracy': accuracy_score(y_test, gb_pred),
                'gb_precision': precision_score(y_test, gb_pred, average='weighted'),
                'gb_recall': recall_score(y_test, gb_pred, average='weighted'),
                'gb_f1': f1_score(y_test, gb_pred, average='weighted')
            }
            
            # 交叉验证
            rf_cv_scores = cross_val_score(self.rf_model, X_scaled, y_encoded, cv=5)
            gb_cv_scores = cross_val_score(self.gb_model, X_scaled, y_encoded, cv=5)
            
            metrics = {
                **rf_metrics,
                **gb_metrics,
                'rf_cv_mean': rf_cv_scores.mean(),
                'rf_cv_std': rf_cv_scores.std(),
                'gb_cv_mean': gb_cv_scores.mean(),
                'gb_cv_std': gb_cv_scores.std()
            }
            
            # 保存模型
            self.save_models()
            self.model_trained = True
            
            logger.info(f"模型训练完成 - RF准确率: {rf_metrics['rf_accuracy']:.3f}, GB准确率: {gb_metrics['gb_accuracy']:.3f}")
            return metrics
            
        except Exception as e:
            logger.error(f"训练模型失败: {e}")
            return {}
    
    def predict_success_probability(self, features: Dict) -> Dict[str, Any]:
        """预测交易成功概率"""
        try:
            if not self.model_trained or self.rf_model is None:
                logger.warning("模型未训练，尝试加载已保存的模型")
                if not self.load_models():
                    logger.warning("模型文件不完整，开始自动训练")
                    self._initialize_default_model()
                    if not self.model_trained:
                        return {'probability': 0.5, 'confidence': 'low', 'model_available': False}
            
            # 准备特征数据
            feature_df = pd.DataFrame([features])
            
            # 确保所有必要特征都存在
            for col in self.feature_columns:
                if col not in feature_df.columns:
                    feature_df[col] = 0  # 默认值
            
            # 重新排序列以匹配训练时的顺序
            feature_df = feature_df[self.feature_columns]
            
            # 处理分类特征
            if 'risk_level' in feature_df.columns:
                risk_mapping = {'low': 0, 'medium': 1, 'high': 2}
                feature_df['risk_level'] = feature_df['risk_level'].map(risk_mapping).fillna(1)
            
            # 标准化特征
            feature_scaled = self.scaler.transform(feature_df)
            
            # 转换回DataFrame以保持特征名称
            feature_scaled_df = pd.DataFrame(feature_scaled, columns=self.feature_columns)
            
            # 预测
            rf_prob = self.rf_model.predict_proba(feature_scaled_df)[0]
            gb_prob = self.gb_model.predict_proba(feature_scaled_df)[0]
            
            # 集成预测（加权平均）
            rf_weight = 0.6
            gb_weight = 0.4
            
            # 假设类别0是'loss'，类别1是'win'
            win_prob = rf_weight * rf_prob[1] + gb_weight * gb_prob[1]
            
            # 获取特征重要性
            feature_importance = self.get_feature_importance()
            
            # 计算预测置信度
            confidence_score = abs(win_prob - 0.5) * 2  # 0-1之间
            confidence_level = 'high' if confidence_score > 0.3 else 'medium' if confidence_score > 0.15 else 'low'
            
            return {
                'probability': float(win_prob),
                'confidence_score': float(confidence_score),
                'confidence_level': confidence_level,
                'rf_probability': float(rf_prob[1]),
                'gb_probability': float(gb_prob[1]),
                'feature_importance': feature_importance,
                'model_available': True
            }
            
        except Exception as e:
            logger.error(f"预测失败: {e}")
            return {
                'probability': 0.5,
                'confidence_score': 0,
                'confidence_level': 'low',
                'model_available': False,
                'error': str(e)
            }
    
    def get_feature_importance(self) -> Dict[str, float]:
        """获取特征重要性"""
        try:
            if self.rf_model is None:
                return {}
            
            importance = self.rf_model.feature_importances_
            feature_importance = dict(zip(self.feature_columns, importance))
            
            # 按重要性排序
            sorted_importance = dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))
            
            return sorted_importance
            
        except Exception as e:
            logger.error(f"获取特征重要性失败: {e}")
            return {}
    
    def save_models(self) -> bool:
        """保存训练好的模型"""
        try:
            if self.rf_model is not None:
                joblib.dump(self.rf_model, os.path.join(self.model_dir, 'rf_model.pkl'))
            
            if self.gb_model is not None:
                joblib.dump(self.gb_model, os.path.join(self.model_dir, 'gb_model.pkl'))
            
            joblib.dump(self.scaler, os.path.join(self.model_dir, 'scaler.pkl'))
            joblib.dump(self.label_encoder, os.path.join(self.model_dir, 'label_encoder.pkl'))
            joblib.dump(self.feature_columns, os.path.join(self.model_dir, 'feature_columns.pkl'))
            
            logger.info("模型保存成功")
            return True
            
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
            return False
    
    def load_models(self) -> bool:
        """加载已保存的模型"""
        try:
            rf_path = os.path.join(self.model_dir, 'rf_model.pkl')
            gb_path = os.path.join(self.model_dir, 'gb_model.pkl')
            scaler_path = os.path.join(self.model_dir, 'scaler.pkl')
            encoder_path = os.path.join(self.model_dir, 'label_encoder.pkl')
            features_path = os.path.join(self.model_dir, 'feature_columns.pkl')
            
            if not all(os.path.exists(path) for path in [rf_path, gb_path, scaler_path, encoder_path, features_path]):
                logger.warning("模型文件不完整")
                return False
            
            self.rf_model = joblib.load(rf_path)
            self.gb_model = joblib.load(gb_path)
            self.scaler = joblib.load(scaler_path)
            self.label_encoder = joblib.load(encoder_path)
            self.feature_columns = joblib.load(features_path)
            
            self.model_trained = True
            logger.info("模型加载成功")
            return True
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False
    
    def retrain_model(self, days: int = 90) -> Dict[str, float]:
        """重新训练模型"""
        try:
            logger.info("开始重新训练模型")
            
            # 准备训练数据
            X, y = self.prepare_training_data(days)
            
            if X.empty or y.empty:
                logger.error("无法获取训练数据")
                return {}
            
            # 训练模型
            metrics = self.train_models(X, y)
            
            if metrics:
                logger.info("模型重新训练完成")
            else:
                logger.error("模型重新训练失败")
            
            return metrics
            
        except Exception as e:
            logger.error(f"重新训练模型失败: {e}")
            return {}
    
    def get_model_info(self) -> Dict:
        """获取模型信息"""
        try:
            info = {
                'model_trained': self.model_trained,
                'feature_count': len(self.feature_columns),
                'feature_columns': self.feature_columns,
                'model_files_exist': False
            }
            
            # 检查模型文件是否存在
            model_files = ['rf_model.pkl', 'gb_model.pkl', 'scaler.pkl', 'label_encoder.pkl', 'feature_columns.pkl']
            files_exist = all(os.path.exists(os.path.join(self.model_dir, f)) for f in model_files)
            info['model_files_exist'] = files_exist
            
            if files_exist:
                # 获取文件修改时间
                rf_path = os.path.join(self.model_dir, 'rf_model.pkl')
                info['last_trained'] = datetime.fromtimestamp(os.path.getmtime(rf_path)).isoformat()
            
            return info
            
        except Exception as e:
            logger.error(f"获取模型信息失败: {e}")
            return {'model_trained': False, 'error': str(e)}