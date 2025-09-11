import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, GridSearchCV, RandomizedSearchCV, TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
from sklearn.base import clone
from sklearn.ensemble import VotingClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
import xgboost as xgb
import lightgbm as lgb
import joblib
import os
from core.database import TradingDatabase
from analysis.enhanced_indicators import EnhancedTechnicalIndicators
from trading.okx_client import OKXClient

class TradingPredictionModel:
    """交易预测模型"""
    
    def __init__(self, db_path: str = "trading_data.db", model_dir: str = "models"):
        self.db = TradingDatabase(db_path)
        self.okx_client = OKXClient()
        self.indicators_calculator = EnhancedTechnicalIndicators()
        self.model_dir = model_dir
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.rf_model = None
        self.gb_model = None
        self.xgb_model = None
        self.lgb_model = None
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
            # 技术指标特征
            'rsi_14', 'macd', 'macd_signal', 'macd_histogram', 'bb_width', 'kdj_k', 'kdj_d', 'kdj_j',
            'williams_r', 'cci', 'atr_percent', 'volatility', 'volatility_percentile', 'adx', 'trend_strength',
            
            # 价格特征
            'price_change_1h', 'price_change_4h', 'price_change_24h_past',
            
            # 滞后特征
            'price_change_lag1', 'price_change_lag2', 'price_change_lag3',
            
            # 滑动窗口统计特征
            'price_ma_5', 'price_ma_10', 'price_ma_20', 'price_std_5', 'price_std_10',
            
            # 价格位置特征
            'price_position_5d', 'price_position_10d',
            
            # 成交量特征
            'volume_ratio', 'volume_ma_5', 'volume_ma_10', 'volume_std_5', 
            'volume_change_1h', 'volume_lag1', 'volume_lag2',
            
            # 时间特征
            'hour_of_day', 'day_of_week', 'day_of_month'
        ]
        # 训练一个基础模型
        X, y = self.prepare_training_data(30)  # 使用较少天数的模拟数据
        if not X.empty and not y.empty:
            self.train_models(X, y)
            self.save_models()
    
    def prepare_training_data(self, days: int = 365) -> Tuple[pd.DataFrame, pd.Series]:
        """准备训练数据 - 使用真实的OKX历史数据"""
        try:
            logger.info(f"准备 {days} 天的真实历史训练数据")
            
            # 获取真实的历史数据
            training_data = self._get_real_historical_data(days)
            
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
    
    def _get_real_historical_data(self, days: int = 365) -> pd.DataFrame:
        """获取真实的OKX历史数据用于训练"""
        try:
            logger.info(f"开始获取 {days} 天的真实历史数据")
            
            # 主要交易对列表
            symbols = ['BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'BNB-USDT-SWAP', 'SOL-USDT-SWAP', 'ADA-USDT-SWAP']
            all_training_data = []
            
            for symbol in symbols:
                logger.info(f"获取 {symbol} 的历史数据")
                
                # 获取历史K线数据（1小时周期）
                kline_data = self.okx_client.get_kline_data(symbol, '1h', limit=days * 24)
                
                if kline_data is None or kline_data.empty:
                    logger.warning(f"无法获取 {symbol} 的K线数据")
                    continue
                
                # 计算技术指标
                indicators = self.indicators_calculator.calculate_all_indicators(kline_data)
                
                if not indicators:
                    logger.warning(f"无法计算 {symbol} 的技术指标")
                    continue
                
                # 准备训练样本
                symbol_data = self._prepare_symbol_training_data(symbol, kline_data, indicators)
                
                if not symbol_data.empty:
                    all_training_data.append(symbol_data)
                    logger.info(f"成功处理 {symbol}，获得 {len(symbol_data)} 条训练样本")
            
            if not all_training_data:
                logger.error("未能获取任何有效的历史数据")
                return pd.DataFrame()
            
            # 合并所有数据
            combined_data = pd.concat(all_training_data, ignore_index=True)
            logger.info(f"总共获得 {len(combined_data)} 条训练样本")
            
            return combined_data
            
        except Exception as e:
            logger.error(f"获取真实历史数据失败: {e}")
            return pd.DataFrame()
    
    def _prepare_symbol_training_data(self, symbol: str, kline_data: pd.DataFrame, indicators: Dict) -> pd.DataFrame:
        """为单个交易对准备训练数据"""
        try:
            training_samples = []
            
            # 确保有足够的数据点
            if len(kline_data) < 100:
                return pd.DataFrame()
            
            # 遍历历史数据，创建训练样本
            for i in range(50, len(kline_data) - 24):  # 留出前50个点用于指标计算，后24个点用于验证结果
                current_time = kline_data.index[i]  # timestamp是索引
                current_price = kline_data.iloc[i]['close']
                
                # 获取未来24小时的价格变化（用作标签）
                future_price = kline_data.iloc[i + 24]['close']
                price_change_24h = (future_price - current_price) / current_price * 100
                
                # 创建特征向量（使用扁平化的指标键名）
                features = {
                    'symbol': symbol,
                    'timestamp': current_time,
                    
                    # 技术指标特征（使用扁平化键名）
                    'rsi_14': indicators.get('rsi_14', 50),
                    'macd': indicators.get('macd', 0),
                    'macd_signal': indicators.get('macd_signal', 0),
                    'macd_histogram': indicators.get('macd_histogram', 0),
                    'bb_upper': indicators.get('bb_upper', current_price),
                    'bb_middle': indicators.get('bb_middle', current_price),
                    'bb_lower': indicators.get('bb_lower', current_price),
                    'bb_width': indicators.get('bb_width', 0),
                    'kdj_k': indicators.get('kdj_k', 50),
                    'kdj_d': indicators.get('kdj_d', 50),
                    'kdj_j': indicators.get('kdj_j', 50),
                    'williams_r': indicators.get('williams_r', -50),
                    'cci': indicators.get('cci', 0),
                    'atr': indicators.get('atr', 0),
                    'atr_percent': indicators.get('atr_percent', 1),
                    
                    # 价格相关特征
                    'price_change_1h': (kline_data.iloc[i]['close'] - kline_data.iloc[i-1]['close']) / kline_data.iloc[i-1]['close'] * 100 if i > 0 else 0,
                    'price_change_4h': (kline_data.iloc[i]['close'] - kline_data.iloc[i-4]['close']) / kline_data.iloc[i-4]['close'] * 100 if i >= 4 else 0,
                    'price_change_24h_past': (kline_data.iloc[i]['close'] - kline_data.iloc[i-24]['close']) / kline_data.iloc[i-24]['close'] * 100 if i >= 24 else 0,
                    
                    # 滞后特征（前几个时间点的价格变化）
                    'price_change_lag1': (kline_data.iloc[i-1]['close'] - kline_data.iloc[i-2]['close']) / kline_data.iloc[i-2]['close'] * 100 if i >= 2 else 0,
                    'price_change_lag2': (kline_data.iloc[i-2]['close'] - kline_data.iloc[i-3]['close']) / kline_data.iloc[i-3]['close'] * 100 if i >= 3 else 0,
                    'price_change_lag3': (kline_data.iloc[i-3]['close'] - kline_data.iloc[i-4]['close']) / kline_data.iloc[i-4]['close'] * 100 if i >= 4 else 0,
                    
                    # 滑动窗口统计特征
                    'price_ma_5': kline_data.iloc[i-4:i+1]['close'].mean() if i >= 4 else current_price,
                    'price_ma_10': kline_data.iloc[i-9:i+1]['close'].mean() if i >= 9 else current_price,
                    'price_ma_20': kline_data.iloc[i-19:i+1]['close'].mean() if i >= 19 else current_price,
                    'price_std_5': kline_data.iloc[i-4:i+1]['close'].std() if i >= 4 else 0,
                    'price_std_10': kline_data.iloc[i-9:i+1]['close'].std() if i >= 9 else 0,
                    
                    # 价格位置特征
                    'price_position_5d': (current_price - kline_data.iloc[i-4:i+1]['close'].min()) / (kline_data.iloc[i-4:i+1]['close'].max() - kline_data.iloc[i-4:i+1]['close'].min()) if i >= 4 and kline_data.iloc[i-4:i+1]['close'].max() != kline_data.iloc[i-4:i+1]['close'].min() else 0.5,
                    'price_position_10d': (current_price - kline_data.iloc[i-9:i+1]['close'].min()) / (kline_data.iloc[i-9:i+1]['close'].max() - kline_data.iloc[i-9:i+1]['close'].min()) if i >= 9 and kline_data.iloc[i-9:i+1]['close'].max() != kline_data.iloc[i-9:i+1]['close'].min() else 0.5,
                    
                    # 成交量特征
                    'volume': kline_data.iloc[i]['volume'],
                    'volume_ratio': kline_data.iloc[i]['volume'] / kline_data.iloc[i-24:i]['volume'].mean() if i >= 24 else 1,
                    'volume_ma_5': kline_data.iloc[i-4:i+1]['volume'].mean() if i >= 4 else kline_data.iloc[i]['volume'],
                    'volume_ma_10': kline_data.iloc[i-9:i+1]['volume'].mean() if i >= 9 else kline_data.iloc[i]['volume'],
                    'volume_std_5': kline_data.iloc[i-4:i+1]['volume'].std() if i >= 4 else 0,
                    'volume_change_1h': (kline_data.iloc[i]['volume'] - kline_data.iloc[i-1]['volume']) / kline_data.iloc[i-1]['volume'] * 100 if i > 0 and kline_data.iloc[i-1]['volume'] > 0 else 0,
                    'volume_lag1': kline_data.iloc[i-1]['volume'] if i >= 1 else kline_data.iloc[i]['volume'],
                    'volume_lag2': kline_data.iloc[i-2]['volume'] if i >= 2 else kline_data.iloc[i]['volume'],
                    
                    # 波动率特征
                    'volatility': indicators.get('volatility', 1),
                    'volatility_percentile': indicators.get('volatility_percentile', 50),
                    
                    # 趋势特征
                    'adx': indicators.get('adx', 25),
                    'trend_strength': indicators.get('trend_strength', 0),
                    
                    # 时间特征
                    'hour_of_day': pd.to_datetime(current_time).hour,
                    'day_of_week': pd.to_datetime(current_time).weekday(),
                    'day_of_month': pd.to_datetime(current_time).day,
                }
                
                # 创建标签（基于未来24小时价格变化）
                if price_change_24h > 2:  # 上涨超过2%
                    outcome = 'win'
                elif price_change_24h < -2:  # 下跌超过2%
                    outcome = 'loss'
                else:  # 横盘
                    outcome = 'neutral'
                
                features['outcome'] = outcome
                features['future_return'] = price_change_24h
                
                training_samples.append(features)
            
            return pd.DataFrame(training_samples)
            
        except Exception as e:
            logger.error(f"准备 {symbol} 训练数据失败: {e}")
            return pd.DataFrame()
    
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
            
            # 训练XGBoost模型
            logger.info("训练XGBoost模型")
            self.xgb_model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                eval_metric='logloss'
            )
            self.xgb_model.fit(X_train, y_train)
            
            # 训练LightGBM模型
            logger.info("训练LightGBM模型")
            self.lgb_model = lgb.LGBMClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                random_state=42,
                verbose=-1
            )
            self.lgb_model.fit(X_train, y_train)
            
            # 评估模型
            rf_pred = self.rf_model.predict(X_test)
            gb_pred = self.gb_model.predict(X_test)
            xgb_pred = self.xgb_model.predict(X_test)
            lgb_pred = self.lgb_model.predict(X_test)
            
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
            
            xgb_metrics = {
                'xgb_accuracy': accuracy_score(y_test, xgb_pred),
                'xgb_precision': precision_score(y_test, xgb_pred, average='weighted'),
                'xgb_recall': recall_score(y_test, xgb_pred, average='weighted'),
                'xgb_f1': f1_score(y_test, xgb_pred, average='weighted')
            }
            
            lgb_metrics = {
                'lgb_accuracy': accuracy_score(y_test, lgb_pred),
                'lgb_precision': precision_score(y_test, lgb_pred, average='weighted'),
                'lgb_recall': recall_score(y_test, lgb_pred, average='weighted'),
                'lgb_f1': f1_score(y_test, lgb_pred, average='weighted')
            }
            
            # 交叉验证
            rf_cv_scores = cross_val_score(self.rf_model, X_scaled, y_encoded, cv=5)
            gb_cv_scores = cross_val_score(self.gb_model, X_scaled, y_encoded, cv=5)
            xgb_cv_scores = cross_val_score(self.xgb_model, X_scaled, y_encoded, cv=5)
            lgb_cv_scores = cross_val_score(self.lgb_model, X_scaled, y_encoded, cv=5)
            
            metrics = {
                **rf_metrics,
                **gb_metrics,
                **xgb_metrics,
                **lgb_metrics,
                'rf_cv_mean': rf_cv_scores.mean(),
                'rf_cv_std': rf_cv_scores.std(),
                'gb_cv_mean': gb_cv_scores.mean(),
                'gb_cv_std': gb_cv_scores.std(),
                'xgb_cv_mean': xgb_cv_scores.mean(),
                'xgb_cv_std': xgb_cv_scores.std(),
                'lgb_cv_mean': lgb_cv_scores.mean(),
                'lgb_cv_std': lgb_cv_scores.std()
            }
            
            # 保存模型
            self.save_models()
            self.model_trained = True
            
            logger.info(f"模型训练完成 - RF: {rf_metrics['rf_accuracy']:.3f}, GB: {gb_metrics['gb_accuracy']:.3f}, XGB: {xgb_metrics['xgb_accuracy']:.3f}, LGB: {lgb_metrics['lgb_accuracy']:.3f}")
            return metrics
            
        except Exception as e:
            logger.error(f"训练模型失败: {e}")
            return {}
    
    def predict_success_probability(self, features: Dict) -> Dict[str, Any]:
        """预测交易成功概率"""
        try:
            if not self.model_trained or self.rf_model is None or self.xgb_model is None:
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
            xgb_prob = self.xgb_model.predict_proba(feature_scaled_df)[0]
            lgb_prob = self.lgb_model.predict_proba(feature_scaled_df)[0]
            
            # 集成预测（加权平均，XGBoost和LightGBM权重更高）
            rf_weight = 0.2
            gb_weight = 0.2
            xgb_weight = 0.3
            lgb_weight = 0.3
            
            # 假设类别0是'loss'，类别1是'win'
            win_prob = (rf_weight * rf_prob[1] + gb_weight * gb_prob[1] + 
                       xgb_weight * xgb_prob[1] + lgb_weight * lgb_prob[1])
            
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
        """获取综合特征重要性（所有模型的加权平均）"""
        try:
            if self.rf_model is None or self.xgb_model is None:
                return {}
            
            # 获取各模型的特征重要性
            rf_importance = self.rf_model.feature_importances_
            gb_importance = self.gb_model.feature_importances_
            xgb_importance = self.xgb_model.feature_importances_
            lgb_importance = self.lgb_model.feature_importances_
            
            # 加权平均（与预测时的权重一致）
            rf_weight, gb_weight, xgb_weight, lgb_weight = 0.2, 0.2, 0.3, 0.3
            
            combined_importance = (
                rf_weight * rf_importance + 
                gb_weight * gb_importance + 
                xgb_weight * xgb_importance + 
                lgb_weight * lgb_importance
            )
            
            feature_importance = dict(zip(self.feature_columns, combined_importance))
            
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
            
            if self.xgb_model is not None:
                joblib.dump(self.xgb_model, os.path.join(self.model_dir, 'xgb_model.pkl'))
            
            if self.lgb_model is not None:
                joblib.dump(self.lgb_model, os.path.join(self.model_dir, 'lgb_model.pkl'))
            
            joblib.dump(self.scaler, os.path.join(self.model_dir, 'scaler.pkl'))
            joblib.dump(self.label_encoder, os.path.join(self.model_dir, 'label_encoder.pkl'))
            joblib.dump(self.feature_columns, os.path.join(self.model_dir, 'feature_columns.pkl'))
            
            logger.info("所有模型保存成功")
            return True
            
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
            return False
    
    def load_models(self) -> bool:
        """加载已保存的模型"""
        try:
            rf_path = os.path.join(self.model_dir, 'rf_model.pkl')
            gb_path = os.path.join(self.model_dir, 'gb_model.pkl')
            xgb_path = os.path.join(self.model_dir, 'xgb_model.pkl')
            lgb_path = os.path.join(self.model_dir, 'lgb_model.pkl')
            scaler_path = os.path.join(self.model_dir, 'scaler.pkl')
            encoder_path = os.path.join(self.model_dir, 'label_encoder.pkl')
            features_path = os.path.join(self.model_dir, 'feature_columns.pkl')
            
            # 检查基础模型文件
            basic_paths = [rf_path, gb_path, scaler_path, encoder_path, features_path]
            if not all(os.path.exists(path) for path in basic_paths):
                logger.warning("基础模型文件不完整")
                return False
            
            # 加载基础模型
            self.rf_model = joblib.load(rf_path)
            self.gb_model = joblib.load(gb_path)
            self.scaler = joblib.load(scaler_path)
            self.label_encoder = joblib.load(encoder_path)
            self.feature_columns = joblib.load(features_path)
            
            # 尝试加载新模型（向后兼容）
            if os.path.exists(xgb_path):
                self.xgb_model = joblib.load(xgb_path)
                logger.info("XGBoost模型加载成功")
            else:
                logger.warning("XGBoost模型文件不存在，将在下次训练时创建")
                
            if os.path.exists(lgb_path):
                self.lgb_model = joblib.load(lgb_path)
                logger.info("LightGBM模型加载成功")
            else:
                logger.warning("LightGBM模型文件不存在，将在下次训练时创建")
            
            self.model_trained = True
            logger.info("模型加载完成")
            return True
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False
    
    def retrain_model(self, days: int = 365) -> Dict[str, float]:
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
    
    def optimize_hyperparameters(self, X: pd.DataFrame, y: pd.Series, method: str = 'grid_search') -> Dict[str, Any]:
        """超参数优化
        
        Args:
            X: 特征数据
            y: 标签数据
            method: 优化方法 ('grid_search' 或 'random_search')
            
        Returns:
            优化结果字典
        """
        try:
            logger.info(f"开始超参数优化，方法: {method}")
            
            if X.empty or y.empty:
                logger.error("训练数据为空")
                return {'success': False, 'error': '训练数据为空'}
            
            # 时间序列交叉验证
            tscv = TimeSeriesSplit(n_splits=3)
            
            # 定义参数网格
            param_grids = {
                'rf': {
                    'n_estimators': [50, 100, 200],
                    'max_depth': [5, 10, 15, None],
                    'min_samples_split': [2, 5, 10],
                    'min_samples_leaf': [1, 2, 4],
                    'max_features': ['sqrt', 'log2', None]
                },
                'gb': {
                    'n_estimators': [50, 100, 200],
                    'learning_rate': [0.01, 0.1, 0.2],
                    'max_depth': [3, 5, 7],
                    'min_samples_split': [2, 5, 10],
                    'min_samples_leaf': [1, 2, 4]
                },
                'xgb': {
                    'n_estimators': [50, 100, 200],
                    'learning_rate': [0.01, 0.1, 0.2],
                    'max_depth': [3, 5, 7],
                    'min_child_weight': [1, 3, 5],
                    'subsample': [0.8, 0.9, 1.0],
                    'colsample_bytree': [0.8, 0.9, 1.0]
                },
                'lgb': {
                    'n_estimators': [50, 100, 200],
                    'learning_rate': [0.01, 0.1, 0.2],
                    'max_depth': [3, 5, 7],
                    'min_child_samples': [10, 20, 30],
                    'subsample': [0.8, 0.9, 1.0],
                    'colsample_bytree': [0.8, 0.9, 1.0]
                }
            }
            
            # 基础模型
            base_models = {
                'rf': RandomForestClassifier(random_state=42),
                'gb': GradientBoostingClassifier(random_state=42),
                'xgb': xgb.XGBClassifier(random_state=42, eval_metric='logloss'),
                'lgb': lgb.LGBMClassifier(random_state=42, verbose=-1)
            }
            
            optimized_params = {}
            best_scores = {}
            
            # 对每个模型进行超参数优化
            for model_name, base_model in base_models.items():
                logger.info(f"优化{model_name}模型超参数...")
                
                try:
                    if method == 'grid_search':
                        # 网格搜索
                        grid_search = GridSearchCV(
                            estimator=base_model,
                            param_grid=param_grids[model_name],
                            cv=tscv,
                            scoring='accuracy',
                            n_jobs=-1,
                            verbose=0
                        )
                        grid_search.fit(X, y)
                        
                        optimized_params[model_name] = grid_search.best_params_
                        best_scores[model_name] = grid_search.best_score_
                        
                        logger.info(f"{model_name}最佳参数: {grid_search.best_params_}")
                        logger.info(f"{model_name}最佳得分: {grid_search.best_score_:.4f}")
                        
                    else:
                        # 随机搜索（简化版本）
                        from sklearn.model_selection import RandomizedSearchCV
                        
                        random_search = RandomizedSearchCV(
                            estimator=base_model,
                            param_distributions=param_grids[model_name],
                            n_iter=20,  # 随机搜索次数
                            cv=tscv,
                            scoring='accuracy',
                            n_jobs=-1,
                            random_state=42,
                            verbose=0
                        )
                        random_search.fit(X, y)
                        
                        optimized_params[model_name] = random_search.best_params_
                        best_scores[model_name] = random_search.best_score_
                        
                        logger.info(f"{model_name}最佳参数: {random_search.best_params_}")
                        logger.info(f"{model_name}最佳得分: {random_search.best_score_:.4f}")
                        
                except Exception as e:
                    logger.error(f"优化{model_name}模型失败: {e}")
                    optimized_params[model_name] = {}
                    best_scores[model_name] = 0.0
            
            # 保存优化结果
            optimization_result = {
                'success': True,
                'method': method,
                'optimized_params': optimized_params,
                'best_scores': best_scores,
                'optimization_time': datetime.now().isoformat()
            }
            
            # 保存到文件
            result_path = os.path.join(self.model_dir, 'hyperparameter_optimization.pkl')
            joblib.dump(optimization_result, result_path)
            logger.info(f"超参数优化结果已保存到: {result_path}")
            
            return optimization_result
            
        except Exception as e:
            logger.error(f"超参数优化失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def train_models_with_optimized_params(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """使用优化后的超参数训练模型"""
        try:
            # 加载优化结果
            result_path = os.path.join(self.model_dir, 'hyperparameter_optimization.pkl')
            if not os.path.exists(result_path):
                logger.warning("未找到超参数优化结果，使用默认参数")
                return self.train_models(X, y)
            
            optimization_result = joblib.load(result_path)
            optimized_params = optimization_result.get('optimized_params', {})
            
            logger.info("使用优化后的超参数训练模型...")
            
            # 数据预处理
            if X.empty or y.empty:
                logger.error("训练数据为空")
                return {}
            
            # 处理分类特征
            categorical_features = ['hour_of_day', 'day_of_week', 'day_of_month']
            for feature in categorical_features:
                if feature in X.columns:
                    X[feature] = X[feature].astype('category')
            
            # 标准化特征
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            X_scaled = pd.DataFrame(X_scaled, columns=X.columns, index=X.index)
            
            # 编码目标变量
            self.label_encoder = LabelEncoder()
            y_encoded = self.label_encoder.fit_transform(y)
            
            # 分割数据
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
            )
            
            # 使用优化参数训练模型
            models_metrics = {}
            
            # Random Forest
            rf_params = optimized_params.get('rf', {})
            self.rf_model = RandomForestClassifier(random_state=42, **rf_params)
            self.rf_model.fit(X_train, y_train)
            rf_pred = self.rf_model.predict(X_test)
            models_metrics['rf'] = self._calculate_metrics(y_test, rf_pred)
            
            # Gradient Boosting
            gb_params = optimized_params.get('gb', {})
            self.gb_model = GradientBoostingClassifier(random_state=42, **gb_params)
            self.gb_model.fit(X_train, y_train)
            gb_pred = self.gb_model.predict(X_test)
            models_metrics['gb'] = self._calculate_metrics(y_test, gb_pred)
            
            # XGBoost
            xgb_params = optimized_params.get('xgb', {})
            self.xgb_model = xgb.XGBClassifier(random_state=42, eval_metric='logloss', **xgb_params)
            self.xgb_model.fit(X_train, y_train)
            xgb_pred = self.xgb_model.predict(X_test)
            models_metrics['xgb'] = self._calculate_metrics(y_test, xgb_pred)
            
            # LightGBM
            lgb_params = optimized_params.get('lgb', {})
            self.lgb_model = lgb.LGBMClassifier(random_state=42, verbose=-1, **lgb_params)
            self.lgb_model.fit(X_train, y_train)
            lgb_pred = self.lgb_model.predict(X_test)
            models_metrics['lgb'] = self._calculate_metrics(y_test, lgb_pred)
            
            # 保存特征列名
            self.feature_columns = list(X.columns)
            
            # 标记模型已训练
            self.model_trained = True
            
            # 整合所有指标
            metrics = {
                'rf_accuracy': models_metrics['rf']['accuracy'],
                'gb_accuracy': models_metrics['gb']['accuracy'],
                'xgb_accuracy': models_metrics['xgb']['accuracy'],
                'lgb_accuracy': models_metrics['lgb']['accuracy'],
                'rf_precision': models_metrics['rf']['precision'],
                'gb_precision': models_metrics['gb']['precision'],
                'xgb_precision': models_metrics['xgb']['precision'],
                'lgb_precision': models_metrics['lgb']['precision'],
                'rf_recall': models_metrics['rf']['recall'],
                'gb_recall': models_metrics['gb']['recall'],
                'xgb_recall': models_metrics['xgb']['recall'],
                'lgb_recall': models_metrics['lgb']['recall'],
                'rf_f1': models_metrics['rf']['f1'],
                'gb_f1': models_metrics['gb']['f1'],
                'xgb_f1': models_metrics['xgb']['f1'],
                'lgb_f1': models_metrics['lgb']['f1']
            }
            
            logger.info(f"优化模型训练完成 - RF: {metrics['rf_accuracy']:.4f}, GB: {metrics['gb_accuracy']:.4f}, XGB: {metrics['xgb_accuracy']:.4f}, LGB: {metrics['lgb_accuracy']:.4f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"使用优化参数训练模型失败: {e}")
            return {}
    
    def _calculate_metrics(self, y_true, y_pred) -> Dict[str, float]:
        """计算模型评估指标"""
        return {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y_true, y_pred, average='weighted', zero_division=0),
            'f1': f1_score(y_true, y_pred, average='weighted', zero_division=0)
        }
    
    def time_series_cross_validation(self, X: pd.DataFrame, y: pd.Series, n_splits: int = 5) -> Dict[str, Any]:
        """时间序列交叉验证
        
        Args:
            X: 特征数据
            y: 标签数据
            n_splits: 交叉验证折数
            
        Returns:
            交叉验证结果
        """
        try:
            logger.info(f"开始时间序列交叉验证，折数: {n_splits}")
            
            if X.empty or y.empty:
                logger.error("验证数据为空")
                return {'success': False, 'error': '验证数据为空'}
            
            # 时间序列交叉验证器
            tscv = TimeSeriesSplit(n_splits=n_splits)
            
            # 存储每个模型的交叉验证结果
            cv_results = {
                'rf': {'accuracy': [], 'precision': [], 'recall': [], 'f1': []},
                'gb': {'accuracy': [], 'precision': [], 'recall': [], 'f1': []},
                'xgb': {'accuracy': [], 'precision': [], 'recall': [], 'f1': []},
                'lgb': {'accuracy': [], 'precision': [], 'recall': [], 'f1': []}
            }
            
            # 数据预处理
            scaler = StandardScaler()
            label_encoder = LabelEncoder()
            
            # 处理分类特征
            categorical_features = ['hour_of_day', 'day_of_week', 'day_of_month']
            X_processed = X.copy()
            for feature in categorical_features:
                if feature in X_processed.columns:
                    X_processed[feature] = X_processed[feature].astype('category')
            
            # 标准化和编码
            X_scaled = scaler.fit_transform(X_processed)
            X_scaled = pd.DataFrame(X_scaled, columns=X_processed.columns, index=X_processed.index)
            y_encoded = label_encoder.fit_transform(y)
            
            # 基础模型
            models = {
                'rf': RandomForestClassifier(random_state=42, n_estimators=100),
                'gb': GradientBoostingClassifier(random_state=42, n_estimators=100),
                'xgb': xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_estimators=100),
                'lgb': lgb.LGBMClassifier(random_state=42, verbose=-1, n_estimators=100)
            }
            
            # 执行交叉验证
            fold = 1
            for train_idx, test_idx in tscv.split(X_scaled):
                logger.info(f"执行第{fold}折交叉验证...")
                
                X_train_fold, X_test_fold = X_scaled.iloc[train_idx], X_scaled.iloc[test_idx]
                y_train_fold, y_test_fold = y_encoded[train_idx], y_encoded[test_idx]
                
                # 训练和评估每个模型
                for model_name, model in models.items():
                    try:
                        # 训练模型
                        model_clone = clone(model)
                        model_clone.fit(X_train_fold, y_train_fold)
                        
                        # 预测
                        y_pred = model_clone.predict(X_test_fold)
                        
                        # 计算指标
                        metrics = self._calculate_metrics(y_test_fold, y_pred)
                        
                        # 存储结果
                        for metric_name, value in metrics.items():
                            cv_results[model_name][metric_name].append(value)
                            
                    except Exception as e:
                        logger.error(f"第{fold}折{model_name}模型验证失败: {e}")
                        # 添加默认值
                        for metric_name in ['accuracy', 'precision', 'recall', 'f1']:
                            cv_results[model_name][metric_name].append(0.0)
                
                fold += 1
            
            # 计算平均值和标准差
            cv_summary = {}
            for model_name, results in cv_results.items():
                cv_summary[model_name] = {}
                for metric_name, values in results.items():
                    cv_summary[model_name][f'{metric_name}_mean'] = np.mean(values)
                    cv_summary[model_name][f'{metric_name}_std'] = np.std(values)
                    cv_summary[model_name][f'{metric_name}_scores'] = values
            
            # 生成验证报告
            validation_result = {
                'success': True,
                'n_splits': n_splits,
                'cv_results': cv_results,
                'cv_summary': cv_summary,
                'validation_time': datetime.now().isoformat()
            }
            
            # 保存验证结果
            result_path = os.path.join(self.model_dir, 'time_series_cv_results.pkl')
            joblib.dump(validation_result, result_path)
            logger.info(f"时间序列交叉验证结果已保存到: {result_path}")
            
            # 打印摘要
            logger.info("时间序列交叉验证结果摘要:")
            for model_name, summary in cv_summary.items():
                logger.info(f"{model_name.upper()}: 准确率={summary['accuracy_mean']:.4f}±{summary['accuracy_std']:.4f}, "
                           f"F1={summary['f1_mean']:.4f}±{summary['f1_std']:.4f}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"时间序列交叉验证失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def walk_forward_validation(self, X: pd.DataFrame, y: pd.Series, window_size: int = 100, step_size: int = 20) -> Dict[str, Any]:
        """滑动窗口验证（Walk-Forward Validation）
        
        Args:
            X: 特征数据
            y: 标签数据
            window_size: 训练窗口大小
            step_size: 步长
            
        Returns:
            验证结果
        """
        try:
            logger.info(f"开始滑动窗口验证，窗口大小: {window_size}, 步长: {step_size}")
            
            if X.empty or y.empty or len(X) < window_size + step_size:
                logger.error("验证数据不足")
                return {'success': False, 'error': '验证数据不足'}
            
            # 存储验证结果
            wf_results = {
                'rf': {'accuracy': [], 'precision': [], 'recall': [], 'f1': []},
                'gb': {'accuracy': [], 'precision': [], 'recall': [], 'f1': []},
                'xgb': {'accuracy': [], 'precision': [], 'recall': [], 'f1': []},
                'lgb': {'accuracy': [], 'precision': [], 'recall': [], 'f1': []}
            }
            
            # 数据预处理
            scaler = StandardScaler()
            label_encoder = LabelEncoder()
            
            # 处理分类特征
            categorical_features = ['hour_of_day', 'day_of_week', 'day_of_month']
            X_processed = X.copy()
            for feature in categorical_features:
                if feature in X_processed.columns:
                    X_processed[feature] = X_processed[feature].astype('category')
            
            # 基础模型
            models = {
                'rf': RandomForestClassifier(random_state=42, n_estimators=50),
                'gb': GradientBoostingClassifier(random_state=42, n_estimators=50),
                'xgb': xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_estimators=50),
                'lgb': lgb.LGBMClassifier(random_state=42, verbose=-1, n_estimators=50)
            }
            
            # 滑动窗口验证
            start_idx = 0
            window_count = 1
            
            while start_idx + window_size + step_size <= len(X_processed):
                logger.info(f"执行第{window_count}个窗口验证...")
                
                # 定义训练和测试集
                train_end = start_idx + window_size
                test_start = train_end
                test_end = test_start + step_size
                
                X_train_window = X_processed.iloc[start_idx:train_end]
                y_train_window = y.iloc[start_idx:train_end]
                X_test_window = X_processed.iloc[test_start:test_end]
                y_test_window = y.iloc[test_start:test_end]
                
                # 数据预处理
                X_train_scaled = scaler.fit_transform(X_train_window)
                X_test_scaled = scaler.transform(X_test_window)
                
                X_train_scaled = pd.DataFrame(X_train_scaled, columns=X_train_window.columns)
                X_test_scaled = pd.DataFrame(X_test_scaled, columns=X_test_window.columns)
                
                y_train_encoded = label_encoder.fit_transform(y_train_window)
                y_test_encoded = label_encoder.transform(y_test_window)
                
                # 训练和评估每个模型
                for model_name, model in models.items():
                    try:
                        # 训练模型
                        model_clone = clone(model)
                        model_clone.fit(X_train_scaled, y_train_encoded)
                        
                        # 预测
                        y_pred = model_clone.predict(X_test_scaled)
                        
                        # 计算指标
                        metrics = self._calculate_metrics(y_test_encoded, y_pred)
                        
                        # 存储结果
                        for metric_name, value in metrics.items():
                            wf_results[model_name][metric_name].append(value)
                            
                    except Exception as e:
                        logger.error(f"第{window_count}个窗口{model_name}模型验证失败: {e}")
                        # 添加默认值
                        for metric_name in ['accuracy', 'precision', 'recall', 'f1']:
                            wf_results[model_name][metric_name].append(0.0)
                
                start_idx += step_size
                window_count += 1
            
            # 计算平均值和标准差
            wf_summary = {}
            for model_name, results in wf_results.items():
                wf_summary[model_name] = {}
                for metric_name, values in results.items():
                    if values:  # 确保有数据
                        wf_summary[model_name][f'{metric_name}_mean'] = np.mean(values)
                        wf_summary[model_name][f'{metric_name}_std'] = np.std(values)
                        wf_summary[model_name][f'{metric_name}_scores'] = values
                    else:
                        wf_summary[model_name][f'{metric_name}_mean'] = 0.0
                        wf_summary[model_name][f'{metric_name}_std'] = 0.0
                        wf_summary[model_name][f'{metric_name}_scores'] = []
            
            # 生成验证报告
            validation_result = {
                'success': True,
                'window_size': window_size,
                'step_size': step_size,
                'total_windows': window_count - 1,
                'wf_results': wf_results,
                'wf_summary': wf_summary,
                'validation_time': datetime.now().isoformat()
            }
            
            # 保存验证结果
            result_path = os.path.join(self.model_dir, 'walk_forward_validation_results.pkl')
            joblib.dump(validation_result, result_path)
            logger.info(f"滑动窗口验证结果已保存到: {result_path}")
            
            # 打印摘要
            logger.info("滑动窗口验证结果摘要:")
            for model_name, summary in wf_summary.items():
                logger.info(f"{model_name.upper()}: 准确率={summary['accuracy_mean']:.4f}±{summary['accuracy_std']:.4f}, "
                           f"F1={summary['f1_mean']:.4f}±{summary['f1_std']:.4f}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"滑动窗口验证失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_ensemble_models(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        """创建集成模型：投票分类器和堆叠集成
        
        Args:
            X: 特征数据
            y: 标签数据
            
        Returns:
            集成模型训练结果
        """
        try:
            logger.info("开始创建集成模型...")
            
            if X.empty or y.empty:
                logger.error("训练数据为空")
                return {'success': False, 'error': '训练数据为空'}
            
            # 数据预处理
            scaler = StandardScaler()
            label_encoder = LabelEncoder()
            
            # 处理分类特征
            categorical_features = ['hour_of_day', 'day_of_week', 'day_of_month']
            X_processed = X.copy()
            for feature in categorical_features:
                if feature in X_processed.columns:
                    X_processed[feature] = X_processed[feature].astype('category')
            
            # 标准化和编码
            X_scaled = scaler.fit_transform(X_processed)
            X_scaled = pd.DataFrame(X_scaled, columns=X_processed.columns, index=X_processed.index)
            y_encoded = label_encoder.fit_transform(y)
            
            # 分割数据
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
            )
            
            # 基础模型
            base_models = {
                'rf': RandomForestClassifier(random_state=42, n_estimators=100),
                'gb': GradientBoostingClassifier(random_state=42, n_estimators=100),
                'xgb': xgb.XGBClassifier(random_state=42, eval_metric='logloss', n_estimators=100),
                'lgb': lgb.LGBMClassifier(random_state=42, verbose=-1, n_estimators=100)
            }
            
            # 训练基础模型
            trained_models = {}
            base_predictions = {}
            
            logger.info("训练基础模型...")
            for name, model in base_models.items():
                try:
                    model.fit(X_train, y_train)
                    trained_models[name] = model
                    
                    # 获取预测结果
                    y_pred = model.predict(X_test)
                    base_predictions[name] = {
                        'predictions': y_pred,
                        'accuracy': accuracy_score(y_test, y_pred),
                        'f1': f1_score(y_test, y_pred, average='weighted')
                    }
                    
                    logger.info(f"{name.upper()}模型 - 准确率: {base_predictions[name]['accuracy']:.4f}, F1: {base_predictions[name]['f1']:.4f}")
                    
                except Exception as e:
                    logger.error(f"训练{name}模型失败: {e}")
                    continue
            
            if len(trained_models) < 2:
                logger.error("可用的基础模型不足，无法创建集成模型")
                return {'success': False, 'error': '可用的基础模型不足'}
            
            # 创建投票分类器
            logger.info("创建投票分类器...")
            voting_estimators = [(name, model) for name, model in trained_models.items()]
            
            # 硬投票
            hard_voting_clf = VotingClassifier(
                estimators=voting_estimators,
                voting='hard'
            )
            
            # 软投票
            soft_voting_clf = VotingClassifier(
                estimators=voting_estimators,
                voting='soft'
            )
            
            # 训练投票分类器
            ensemble_results = {}
            
            try:
                hard_voting_clf.fit(X_train, y_train)
                y_pred_hard = hard_voting_clf.predict(X_test)
                ensemble_results['hard_voting'] = {
                    'model': hard_voting_clf,
                    'predictions': y_pred_hard,
                    'accuracy': accuracy_score(y_test, y_pred_hard),
                    'f1': f1_score(y_test, y_pred_hard, average='weighted')
                }
                logger.info(f"硬投票分类器 - 准确率: {ensemble_results['hard_voting']['accuracy']:.4f}, F1: {ensemble_results['hard_voting']['f1']:.4f}")
            except Exception as e:
                logger.error(f"硬投票分类器训练失败: {e}")
            
            try:
                soft_voting_clf.fit(X_train, y_train)
                y_pred_soft = soft_voting_clf.predict(X_test)
                ensemble_results['soft_voting'] = {
                    'model': soft_voting_clf,
                    'predictions': y_pred_soft,
                    'accuracy': accuracy_score(y_test, y_pred_soft),
                    'f1': f1_score(y_test, y_pred_soft, average='weighted')
                }
                logger.info(f"软投票分类器 - 准确率: {ensemble_results['soft_voting']['accuracy']:.4f}, F1: {ensemble_results['soft_voting']['f1']:.4f}")
            except Exception as e:
                logger.error(f"软投票分类器训练失败: {e}")
            
            # 创建堆叠集成
            logger.info("创建堆叠集成模型...")
            try:
                # 使用逻辑回归作为元学习器
                meta_learner = LogisticRegression(random_state=42, max_iter=1000)
                
                stacking_clf = StackingClassifier(
                    estimators=voting_estimators,
                    final_estimator=meta_learner,
                    cv=5,  # 5折交叉验证
                    stack_method='predict_proba',
                    n_jobs=-1
                )
                
                stacking_clf.fit(X_train, y_train)
                y_pred_stack = stacking_clf.predict(X_test)
                
                ensemble_results['stacking'] = {
                    'model': stacking_clf,
                    'predictions': y_pred_stack,
                    'accuracy': accuracy_score(y_test, y_pred_stack),
                    'f1': f1_score(y_test, y_pred_stack, average='weighted')
                }
                logger.info(f"堆叠集成模型 - 准确率: {ensemble_results['stacking']['accuracy']:.4f}, F1: {ensemble_results['stacking']['f1']:.4f}")
                
            except Exception as e:
                logger.error(f"堆叠集成模型训练失败: {e}")
            
            # 保存集成模型
            ensemble_models_path = os.path.join(self.model_dir, 'ensemble_models.pkl')
            models_to_save = {}
            for name, result in ensemble_results.items():
                if 'model' in result:
                    models_to_save[name] = result['model']
            
            if models_to_save:
                joblib.dump({
                    'models': models_to_save,
                    'scaler': scaler,
                    'label_encoder': label_encoder,
                    'feature_columns': X_processed.columns.tolist()
                }, ensemble_models_path)
                logger.info(f"集成模型已保存到: {ensemble_models_path}")
            
            # 生成结果报告
            result = {
                'success': True,
                'base_models': base_predictions,
                'ensemble_results': {name: {k: v for k, v in result.items() if k != 'model'} 
                                   for name, result in ensemble_results.items()},
                'best_model': None,
                'training_time': datetime.now().isoformat()
            }
            
            # 找出最佳模型
            all_results = {**base_predictions, **{name: result for name, result in ensemble_results.items() if 'accuracy' in result}}
            if all_results:
                best_model_name = max(all_results.keys(), key=lambda x: all_results[x]['accuracy'])
                result['best_model'] = {
                    'name': best_model_name,
                    'accuracy': all_results[best_model_name]['accuracy'],
                    'f1': all_results[best_model_name]['f1']
                }
                logger.info(f"最佳模型: {best_model_name.upper()} - 准确率: {result['best_model']['accuracy']:.4f}")
            
            # 保存结果
            result_path = os.path.join(self.model_dir, 'ensemble_results.pkl')
            joblib.dump(result, result_path)
            logger.info(f"集成模型结果已保存到: {result_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"创建集成模型失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def predict_with_ensemble(self, X: pd.DataFrame, model_type: str = 'best') -> Dict[str, Any]:
        """使用集成模型进行预测
        
        Args:
            X: 特征数据
            model_type: 模型类型 ('hard_voting', 'soft_voting', 'stacking', 'best')
            
        Returns:
            预测结果
        """
        try:
            logger.info(f"使用集成模型进行预测，模型类型: {model_type}")
            
            # 加载集成模型
            ensemble_models_path = os.path.join(self.model_dir, 'ensemble_models.pkl')
            if not os.path.exists(ensemble_models_path):
                logger.error("集成模型文件不存在，请先训练集成模型")
                return {'success': False, 'error': '集成模型文件不存在'}
            
            ensemble_data = joblib.load(ensemble_models_path)
            models = ensemble_data['models']
            scaler = ensemble_data['scaler']
            label_encoder = ensemble_data['label_encoder']
            feature_columns = ensemble_data['feature_columns']
            
            # 数据预处理
            X_processed = X.copy()
            
            # 确保特征列一致
            for col in feature_columns:
                if col not in X_processed.columns:
                    X_processed[col] = 0  # 缺失特征用0填充
            
            X_processed = X_processed[feature_columns]  # 保持特征顺序一致
            
            # 处理分类特征
            categorical_features = ['hour_of_day', 'day_of_week', 'day_of_month']
            for feature in categorical_features:
                if feature in X_processed.columns:
                    X_processed[feature] = X_processed[feature].astype('category')
            
            # 标准化
            X_scaled = scaler.transform(X_processed)
            X_scaled = pd.DataFrame(X_scaled, columns=feature_columns, index=X_processed.index)
            
            # 选择模型
            if model_type == 'best':
                # 加载结果文件确定最佳模型
                result_path = os.path.join(self.model_dir, 'ensemble_results.pkl')
                if os.path.exists(result_path):
                    results = joblib.load(result_path)
                    if results.get('best_model'):
                        model_type = results['best_model']['name']
                    else:
                        model_type = 'soft_voting'  # 默认使用软投票
                else:
                    model_type = 'soft_voting'  # 默认使用软投票
            
            if model_type not in models:
                available_models = list(models.keys())
                logger.warning(f"模型类型 {model_type} 不存在，使用 {available_models[0]}")
                model_type = available_models[0]
            
            # 进行预测
            model = models[model_type]
            predictions_encoded = model.predict(X_scaled)
            predictions_proba = None
            
            # 获取预测概率（如果支持）
            try:
                predictions_proba = model.predict_proba(X_scaled)
            except:
                logger.warning(f"模型 {model_type} 不支持概率预测")
            
            # 解码预测结果
            predictions = label_encoder.inverse_transform(predictions_encoded)
            
            result = {
                'success': True,
                'model_type': model_type,
                'predictions': predictions.tolist(),
                'predictions_encoded': predictions_encoded.tolist(),
                'predictions_proba': predictions_proba.tolist() if predictions_proba is not None else None,
                'prediction_time': datetime.now().isoformat()
            }
            
            logger.info(f"预测完成，使用模型: {model_type}，预测样本数: {len(predictions)}")
            return result
            
        except Exception as e:
            logger.error(f"集成模型预测失败: {e}")
            return {'success': False, 'error': str(e)}