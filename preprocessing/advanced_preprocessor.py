import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.covariance import EllipticEnvelope
from sklearn.svm import OneClassSVM
from typing import Dict, List, Tuple, Optional, Any, Union
from loguru import logger
import joblib
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class AdvancedDataPreprocessor:
    """高级数据预处理器
    
    提供异常值检测、数据清洗、特征缩放等高级预处理功能
    """
    
    def __init__(self, output_dir: str = "preprocessing_results"):
        """
        初始化高级数据预处理器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 预处理器存储
        self.scalers = {}
        self.imputers = {}
        self.outlier_detectors = {}
        
        # 处理历史
        self.processing_history = []
        
        # 设置matplotlib中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        logger.info(f"高级数据预处理器初始化完成，输出目录: {output_dir}")
    
    def detect_outliers(self, data: pd.DataFrame, methods: List[str] = None, 
                       contamination: float = 0.1) -> Dict[str, Any]:
        """
        多方法异常值检测
        
        Args:
            data: 输入数据
            methods: 检测方法列表
            contamination: 异常值比例
            
        Returns:
            异常值检测结果
        """
        if methods is None:
            methods = ['isolation_forest', 'z_score', 'iqr', 'elliptic_envelope']
        
        try:
            logger.info(f"开始异常值检测，使用方法: {methods}")
            
            if data.empty:
                logger.error("输入数据为空")
                return {'success': False, 'error': '输入数据为空'}
            
            # 只处理数值列
            numeric_columns = data.select_dtypes(include=[np.number]).columns.tolist()
            if not numeric_columns:
                logger.error("没有找到数值列")
                return {'success': False, 'error': '没有找到数值列'}
            
            numeric_data = data[numeric_columns].copy()
            
            # 处理缺失值（临时）
            numeric_data = numeric_data.fillna(numeric_data.median())
            
            outlier_results = {}
            outlier_masks = {}
            
            # 1. Isolation Forest
            if 'isolation_forest' in methods:
                logger.info("执行Isolation Forest异常值检测...")
                try:
                    iso_forest = IsolationForest(
                        contamination=contamination, 
                        random_state=42, 
                        n_jobs=-1
                    )
                    outlier_pred = iso_forest.fit_predict(numeric_data)
                    outlier_mask = outlier_pred == -1
                    
                    outlier_results['isolation_forest'] = {
                        'outlier_count': np.sum(outlier_mask),
                        'outlier_percentage': np.sum(outlier_mask) / len(data) * 100,
                        'outlier_indices': np.where(outlier_mask)[0].tolist()
                    }
                    outlier_masks['isolation_forest'] = outlier_mask
                    self.outlier_detectors['isolation_forest'] = iso_forest
                    
                    logger.info(f"Isolation Forest检测到 {np.sum(outlier_mask)} 个异常值")
                    
                except Exception as e:
                    logger.error(f"Isolation Forest检测失败: {e}")
            
            # 2. Z-Score方法
            if 'z_score' in methods:
                logger.info("执行Z-Score异常值检测...")
                try:
                    z_scores = np.abs(stats.zscore(numeric_data, axis=0, nan_policy='omit'))
                    outlier_mask = (z_scores > 3).any(axis=1)
                    
                    outlier_results['z_score'] = {
                        'outlier_count': np.sum(outlier_mask),
                        'outlier_percentage': np.sum(outlier_mask) / len(data) * 100,
                        'outlier_indices': np.where(outlier_mask)[0].tolist(),
                        'threshold': 3.0
                    }
                    outlier_masks['z_score'] = outlier_mask
                    
                    logger.info(f"Z-Score检测到 {np.sum(outlier_mask)} 个异常值")
                    
                except Exception as e:
                    logger.error(f"Z-Score检测失败: {e}")
            
            # 3. IQR方法
            if 'iqr' in methods:
                logger.info("执行IQR异常值检测...")
                try:
                    outlier_mask = np.zeros(len(data), dtype=bool)
                    
                    for column in numeric_columns:
                        Q1 = numeric_data[column].quantile(0.25)
                        Q3 = numeric_data[column].quantile(0.75)
                        IQR = Q3 - Q1
                        lower_bound = Q1 - 1.5 * IQR
                        upper_bound = Q3 + 1.5 * IQR
                        
                        column_outliers = (numeric_data[column] < lower_bound) | (numeric_data[column] > upper_bound)
                        outlier_mask = outlier_mask | column_outliers
                    
                    outlier_results['iqr'] = {
                        'outlier_count': np.sum(outlier_mask),
                        'outlier_percentage': np.sum(outlier_mask) / len(data) * 100,
                        'outlier_indices': np.where(outlier_mask)[0].tolist()
                    }
                    outlier_masks['iqr'] = outlier_mask
                    
                    logger.info(f"IQR检测到 {np.sum(outlier_mask)} 个异常值")
                    
                except Exception as e:
                    logger.error(f"IQR检测失败: {e}")
            
            # 4. Elliptic Envelope
            if 'elliptic_envelope' in methods:
                logger.info("执行Elliptic Envelope异常值检测...")
                try:
                    elliptic = EllipticEnvelope(
                        contamination=contamination, 
                        random_state=42
                    )
                    outlier_pred = elliptic.fit_predict(numeric_data)
                    outlier_mask = outlier_pred == -1
                    
                    outlier_results['elliptic_envelope'] = {
                        'outlier_count': np.sum(outlier_mask),
                        'outlier_percentage': np.sum(outlier_mask) / len(data) * 100,
                        'outlier_indices': np.where(outlier_mask)[0].tolist()
                    }
                    outlier_masks['elliptic_envelope'] = outlier_mask
                    self.outlier_detectors['elliptic_envelope'] = elliptic
                    
                    logger.info(f"Elliptic Envelope检测到 {np.sum(outlier_mask)} 个异常值")
                    
                except Exception as e:
                    logger.error(f"Elliptic Envelope检测失败: {e}")
            
            # 5. One-Class SVM
            if 'one_class_svm' in methods:
                logger.info("执行One-Class SVM异常值检测...")
                try:
                    # 对数据进行标准化
                    scaler = StandardScaler()
                    scaled_data = scaler.fit_transform(numeric_data)
                    
                    svm = OneClassSVM(
                        nu=contamination, 
                        kernel='rbf', 
                        gamma='scale'
                    )
                    outlier_pred = svm.fit_predict(scaled_data)
                    outlier_mask = outlier_pred == -1
                    
                    outlier_results['one_class_svm'] = {
                        'outlier_count': np.sum(outlier_mask),
                        'outlier_percentage': np.sum(outlier_mask) / len(data) * 100,
                        'outlier_indices': np.where(outlier_mask)[0].tolist()
                    }
                    outlier_masks['one_class_svm'] = outlier_mask
                    self.outlier_detectors['one_class_svm'] = svm
                    
                    logger.info(f"One-Class SVM检测到 {np.sum(outlier_mask)} 个异常值")
                    
                except Exception as e:
                    logger.error(f"One-Class SVM检测失败: {e}")
            
            # 综合异常值检测结果
            if outlier_masks:
                # 投票机制：多数方法认为是异常值的才标记为异常值
                vote_threshold = max(1, len(outlier_masks) // 2)
                combined_mask = np.zeros(len(data), dtype=bool)
                
                for mask in outlier_masks.values():
                    combined_mask = combined_mask.astype(int) + mask.astype(int)
                
                final_outlier_mask = combined_mask >= vote_threshold
                
                outlier_results['combined'] = {
                    'outlier_count': np.sum(final_outlier_mask),
                    'outlier_percentage': np.sum(final_outlier_mask) / len(data) * 100,
                    'outlier_indices': np.where(final_outlier_mask)[0].tolist(),
                    'vote_threshold': vote_threshold
                }
                outlier_masks['combined'] = final_outlier_mask
            
            # 生成异常值检测报告
            self._plot_outlier_analysis(data, numeric_data, outlier_masks, outlier_results)
            
            # 保存结果
            result = {
                'success': True,
                'outlier_results': outlier_results,
                'outlier_masks': {k: v.tolist() for k, v in outlier_masks.items()},
                'numeric_columns': numeric_columns,
                'detection_methods': methods,
                'contamination': contamination,
                'analysis_time': datetime.now().isoformat()
            }
            
            result_path = os.path.join(self.output_dir, 'outlier_detection_results.pkl')
            joblib.dump(result, result_path)
            logger.info(f"异常值检测结果已保存到: {result_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"异常值检测失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def handle_outliers(self, data: pd.DataFrame, outlier_mask: np.ndarray, 
                       method: str = 'clip', percentile: float = 0.05) -> pd.DataFrame:
        """
        处理异常值
        
        Args:
            data: 输入数据
            outlier_mask: 异常值掩码
            method: 处理方法 ('remove', 'clip', 'transform', 'impute')
            percentile: 截断百分位数
            
        Returns:
            处理后的数据
        """
        try:
            logger.info(f"开始处理异常值，方法: {method}")
            
            if data.empty:
                logger.error("输入数据为空")
                return data
            
            processed_data = data.copy()
            numeric_columns = data.select_dtypes(include=[np.number]).columns.tolist()
            
            if method == 'remove':
                # 移除异常值
                processed_data = processed_data[~outlier_mask]
                logger.info(f"移除了 {np.sum(outlier_mask)} 个异常值")
            
            elif method == 'clip':
                # 截断异常值
                for column in numeric_columns:
                    lower_bound = data[column].quantile(percentile)
                    upper_bound = data[column].quantile(1 - percentile)
                    processed_data[column] = processed_data[column].clip(lower_bound, upper_bound)
                logger.info(f"使用 {percentile*100}% 和 {(1-percentile)*100}% 分位数截断异常值")
            
            elif method == 'transform':
                # 对数变换
                for column in numeric_columns:
                    if (data[column] > 0).all():
                        processed_data[column] = np.log1p(processed_data[column])
                    else:
                        # 使用Box-Cox变换
                        try:
                            processed_data[column], _ = stats.boxcox(processed_data[column] + 1)
                        except:
                            # 如果Box-Cox失败，使用标准化
                            processed_data[column] = (processed_data[column] - processed_data[column].mean()) / processed_data[column].std()
                logger.info("应用了对数/Box-Cox变换")
            
            elif method == 'impute':
                # 用中位数替换异常值
                for column in numeric_columns:
                    median_value = data.loc[~outlier_mask, column].median()
                    processed_data.loc[outlier_mask, column] = median_value
                logger.info(f"用中位数替换了 {np.sum(outlier_mask)} 个异常值")
            
            else:
                logger.error(f"不支持的异常值处理方法: {method}")
                return data
            
            # 记录处理历史
            self.processing_history.append({
                'operation': 'handle_outliers',
                'method': method,
                'outlier_count': np.sum(outlier_mask),
                'original_shape': data.shape,
                'processed_shape': processed_data.shape,
                'timestamp': datetime.now().isoformat()
            })
            
            return processed_data
            
        except Exception as e:
            logger.error(f"处理异常值失败: {e}")
            return data
    
    def handle_missing_values(self, data: pd.DataFrame, strategy: str = 'advanced') -> pd.DataFrame:
        """
        处理缺失值
        
        Args:
            data: 输入数据
            strategy: 处理策略 ('simple', 'advanced', 'knn')
            
        Returns:
            处理后的数据
        """
        try:
            logger.info(f"开始处理缺失值，策略: {strategy}")
            
            if data.empty:
                logger.error("输入数据为空")
                return data
            
            processed_data = data.copy()
            
            # 检查缺失值情况
            missing_info = processed_data.isnull().sum()
            missing_columns = missing_info[missing_info > 0].index.tolist()
            
            if not missing_columns:
                logger.info("没有发现缺失值")
                return processed_data
            
            logger.info(f"发现 {len(missing_columns)} 列存在缺失值")
            
            numeric_columns = processed_data.select_dtypes(include=[np.number]).columns.tolist()
            categorical_columns = processed_data.select_dtypes(include=['object', 'category']).columns.tolist()
            
            if strategy == 'simple':
                # 简单填充策略
                # 数值列用中位数填充
                for column in numeric_columns:
                    if column in missing_columns:
                        median_value = processed_data[column].median()
                        processed_data[column].fillna(median_value, inplace=True)
                
                # 分类列用众数填充
                for column in categorical_columns:
                    if column in missing_columns:
                        mode_value = processed_data[column].mode().iloc[0] if not processed_data[column].mode().empty else 'Unknown'
                        processed_data[column].fillna(mode_value, inplace=True)
                
                logger.info("使用简单填充策略处理缺失值")
            
            elif strategy == 'advanced':
                # 高级填充策略
                # 数值列使用前向填充+后向填充+中位数
                for column in numeric_columns:
                    if column in missing_columns:
                        # 先尝试前向填充
                        processed_data[column].fillna(method='ffill', inplace=True)
                        # 再尝试后向填充
                        processed_data[column].fillna(method='bfill', inplace=True)
                        # 最后用中位数填充剩余的
                        median_value = processed_data[column].median()
                        processed_data[column].fillna(median_value, inplace=True)
                
                # 分类列使用前向填充+众数
                for column in categorical_columns:
                    if column in missing_columns:
                        processed_data[column].fillna(method='ffill', inplace=True)
                        processed_data[column].fillna(method='bfill', inplace=True)
                        mode_value = processed_data[column].mode().iloc[0] if not processed_data[column].mode().empty else 'Unknown'
                        processed_data[column].fillna(mode_value, inplace=True)
                
                logger.info("使用高级填充策略处理缺失值")
            
            elif strategy == 'knn':
                # KNN填充
                if numeric_columns:
                    knn_imputer = KNNImputer(n_neighbors=5)
                    processed_data[numeric_columns] = knn_imputer.fit_transform(processed_data[numeric_columns])
                    self.imputers['knn_numeric'] = knn_imputer
                
                # 分类列仍使用简单策略
                for column in categorical_columns:
                    if column in missing_columns:
                        mode_value = processed_data[column].mode().iloc[0] if not processed_data[column].mode().empty else 'Unknown'
                        processed_data[column].fillna(mode_value, inplace=True)
                
                logger.info("使用KNN填充策略处理缺失值")
            
            else:
                logger.error(f"不支持的缺失值处理策略: {strategy}")
                return data
            
            # 验证处理结果
            remaining_missing = processed_data.isnull().sum().sum()
            if remaining_missing > 0:
                logger.warning(f"仍有 {remaining_missing} 个缺失值未处理")
            else:
                logger.info("所有缺失值已成功处理")
            
            # 记录处理历史
            self.processing_history.append({
                'operation': 'handle_missing_values',
                'strategy': strategy,
                'missing_columns': missing_columns,
                'original_missing_count': missing_info.sum(),
                'remaining_missing_count': remaining_missing,
                'timestamp': datetime.now().isoformat()
            })
            
            return processed_data
            
        except Exception as e:
            logger.error(f"处理缺失值失败: {e}")
            return data
    
    def scale_features(self, data: pd.DataFrame, method: str = 'robust', 
                      feature_columns: List[str] = None) -> Tuple[pd.DataFrame, Any]:
        """
        特征缩放
        
        Args:
            data: 输入数据
            method: 缩放方法 ('standard', 'robust', 'minmax')
            feature_columns: 要缩放的特征列
            
        Returns:
            缩放后的数据和缩放器
        """
        try:
            logger.info(f"开始特征缩放，方法: {method}")
            
            if data.empty:
                logger.error("输入数据为空")
                return data, None
            
            processed_data = data.copy()
            
            if feature_columns is None:
                feature_columns = data.select_dtypes(include=[np.number]).columns.tolist()
            
            if not feature_columns:
                logger.warning("没有找到需要缩放的数值特征")
                return processed_data, None
            
            # 选择缩放器
            if method == 'standard':
                scaler = StandardScaler()
            elif method == 'robust':
                scaler = RobustScaler()
            elif method == 'minmax':
                scaler = MinMaxScaler()
            else:
                logger.error(f"不支持的缩放方法: {method}")
                return data, None
            
            # 执行缩放
            processed_data[feature_columns] = scaler.fit_transform(processed_data[feature_columns])
            
            # 保存缩放器
            self.scalers[method] = scaler
            
            logger.info(f"使用 {method} 方法缩放了 {len(feature_columns)} 个特征")
            
            # 记录处理历史
            self.processing_history.append({
                'operation': 'scale_features',
                'method': method,
                'scaled_columns': feature_columns,
                'timestamp': datetime.now().isoformat()
            })
            
            return processed_data, scaler
            
        except Exception as e:
            logger.error(f"特征缩放失败: {e}")
            return data, None
    
    def _plot_outlier_analysis(self, original_data: pd.DataFrame, numeric_data: pd.DataFrame, 
                              outlier_masks: Dict[str, np.ndarray], outlier_results: Dict[str, Any]):
        """
        绘制异常值分析图表
        
        Args:
            original_data: 原始数据
            numeric_data: 数值数据
            outlier_masks: 异常值掩码字典
            outlier_results: 异常值检测结果
        """
        try:
            logger.info("生成异常值分析图表...")
            
            # 1. 异常值检测结果对比
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            
            # 异常值数量对比
            methods = list(outlier_results.keys())
            counts = [outlier_results[method]['outlier_count'] for method in methods]
            
            axes[0, 0].bar(methods, counts)
            axes[0, 0].set_title('各方法检测到的异常值数量')
            axes[0, 0].set_ylabel('异常值数量')
            axes[0, 0].tick_params(axis='x', rotation=45)
            
            # 异常值百分比对比
            percentages = [outlier_results[method]['outlier_percentage'] for method in methods]
            axes[0, 1].bar(methods, percentages)
            axes[0, 1].set_title('各方法检测到的异常值百分比')
            axes[0, 1].set_ylabel('异常值百分比 (%)')
            axes[0, 1].tick_params(axis='x', rotation=45)
            
            # 异常值分布热图
            if len(outlier_masks) > 1:
                mask_matrix = np.array([mask.astype(int) for mask in outlier_masks.values()])
                sns.heatmap(mask_matrix, xticklabels=False, yticklabels=methods, 
                           cmap='Reds', ax=axes[1, 0])
                axes[1, 0].set_title('异常值检测结果热图')
                axes[1, 0].set_xlabel('样本索引')
            
            # 数据分布箱线图（显示异常值）
            if len(numeric_data.columns) <= 10:
                numeric_data.boxplot(ax=axes[1, 1])
                axes[1, 1].set_title('数值特征箱线图')
                axes[1, 1].tick_params(axis='x', rotation=45)
            else:
                # 如果特征太多，只显示前10个
                numeric_data.iloc[:, :10].boxplot(ax=axes[1, 1])
                axes[1, 1].set_title('数值特征箱线图（前10个）')
                axes[1, 1].tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            
            # 保存图表
            plot_path = os.path.join(self.output_dir, 'outlier_analysis_plots.png')
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 2. 详细的特征分布图
            if len(numeric_data.columns) <= 6:
                fig, axes = plt.subplots(2, 3, figsize=(18, 12))
                axes = axes.flatten()
                
                for i, column in enumerate(numeric_data.columns[:6]):
                    if 'combined' in outlier_masks:
                        outlier_mask = outlier_masks['combined']
                        
                        # 正常值和异常值分别绘制
                        normal_data = numeric_data.loc[~outlier_mask, column]
                        outlier_data = numeric_data.loc[outlier_mask, column]
                        
                        axes[i].hist(normal_data, bins=50, alpha=0.7, label='正常值', color='blue')
                        if len(outlier_data) > 0:
                            axes[i].hist(outlier_data, bins=20, alpha=0.7, label='异常值', color='red')
                        
                        axes[i].set_title(f'{column} 分布')
                        axes[i].set_xlabel('值')
                        axes[i].set_ylabel('频次')
                        axes[i].legend()
                
                plt.tight_layout()
                
                # 保存特征分布图
                dist_plot_path = os.path.join(self.output_dir, 'feature_distribution_plots.png')
                plt.savefig(dist_plot_path, dpi=300, bbox_inches='tight')
                plt.close()
            
            logger.info(f"异常值分析图表已保存到: {plot_path}")
            
        except Exception as e:
            logger.error(f"生成异常值分析图表失败: {e}")
    
    def generate_preprocessing_report(self, original_data: pd.DataFrame, 
                                    processed_data: pd.DataFrame) -> Dict[str, Any]:
        """
        生成预处理报告
        
        Args:
            original_data: 原始数据
            processed_data: 处理后数据
            
        Returns:
            预处理报告
        """
        try:
            logger.info("生成预处理报告...")
            
            report = {
                'success': True,
                'analysis_time': datetime.now().isoformat(),
                'data_summary': {
                    'original_shape': original_data.shape,
                    'processed_shape': processed_data.shape,
                    'shape_change': {
                        'rows_change': processed_data.shape[0] - original_data.shape[0],
                        'cols_change': processed_data.shape[1] - original_data.shape[1]
                    }
                },
                'missing_values': {
                    'original_missing': original_data.isnull().sum().sum(),
                    'processed_missing': processed_data.isnull().sum().sum(),
                    'missing_by_column_original': original_data.isnull().sum().to_dict(),
                    'missing_by_column_processed': processed_data.isnull().sum().to_dict()
                },
                'data_types': {
                    'original_dtypes': original_data.dtypes.astype(str).to_dict(),
                    'processed_dtypes': processed_data.dtypes.astype(str).to_dict()
                },
                'processing_history': self.processing_history,
                'scalers_used': list(self.scalers.keys()),
                'imputers_used': list(self.imputers.keys()),
                'outlier_detectors_used': list(self.outlier_detectors.keys())
            }
            
            # 数值特征统计
            numeric_columns = original_data.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_columns:
                report['numeric_statistics'] = {
                    'original_stats': original_data[numeric_columns].describe().to_dict(),
                    'processed_stats': processed_data[numeric_columns].describe().to_dict() if numeric_columns else {}
                }
            
            # 保存报告
            report_path = os.path.join(self.output_dir, 'preprocessing_report.pkl')
            joblib.dump(report, report_path)
            
            # 生成文本报告
            text_report_path = os.path.join(self.output_dir, 'preprocessing_report.txt')
            self._save_text_preprocessing_report(report, text_report_path)
            
            logger.info(f"预处理报告已保存到: {report_path}")
            
            return report
            
        except Exception as e:
            logger.error(f"生成预处理报告失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _save_text_preprocessing_report(self, report: Dict[str, Any], file_path: str):
        """
        保存文本格式的预处理报告
        
        Args:
            report: 预处理报告
            file_path: 文件路径
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("数据预处理报告\n")
                f.write("=" * 50 + "\n\n")
                
                f.write(f"分析时间: {report['analysis_time']}\n\n")
                
                # 数据概要
                f.write("数据概要:\n")
                f.write("-" * 30 + "\n")
                f.write(f"原始数据形状: {report['data_summary']['original_shape']}\n")
                f.write(f"处理后数据形状: {report['data_summary']['processed_shape']}\n")
                f.write(f"行数变化: {report['data_summary']['shape_change']['rows_change']}\n")
                f.write(f"列数变化: {report['data_summary']['shape_change']['cols_change']}\n\n")
                
                # 缺失值处理
                f.write("缺失值处理:\n")
                f.write("-" * 30 + "\n")
                f.write(f"原始缺失值总数: {report['missing_values']['original_missing']}\n")
                f.write(f"处理后缺失值总数: {report['missing_values']['processed_missing']}\n\n")
                
                # 处理历史
                if report['processing_history']:
                    f.write("处理历史:\n")
                    f.write("-" * 30 + "\n")
                    for i, operation in enumerate(report['processing_history'], 1):
                        f.write(f"{i}. {operation['operation']} - {operation['timestamp']}\n")
                    f.write("\n")
                
                # 使用的工具
                f.write("使用的预处理工具:\n")
                f.write("-" * 30 + "\n")
                f.write(f"缩放器: {', '.join(report['scalers_used']) if report['scalers_used'] else '无'}\n")
                f.write(f"填充器: {', '.join(report['imputers_used']) if report['imputers_used'] else '无'}\n")
                f.write(f"异常值检测器: {', '.join(report['outlier_detectors_used']) if report['outlier_detectors_used'] else '无'}\n")
            
            logger.info(f"文本预处理报告已保存到: {file_path}")
            
        except Exception as e:
            logger.error(f"保存文本预处理报告失败: {e}")
    
    def save_preprocessors(self, file_path: str = None):
        """
        保存预处理器
        
        Args:
            file_path: 保存路径
        """
        try:
            if file_path is None:
                file_path = os.path.join(self.output_dir, 'preprocessors.pkl')
            
            preprocessors = {
                'scalers': self.scalers,
                'imputers': self.imputers,
                'outlier_detectors': self.outlier_detectors,
                'processing_history': self.processing_history
            }
            
            joblib.dump(preprocessors, file_path)
            logger.info(f"预处理器已保存到: {file_path}")
            
        except Exception as e:
            logger.error(f"保存预处理器失败: {e}")
    
    def load_preprocessors(self, file_path: str):
        """
        加载预处理器
        
        Args:
            file_path: 文件路径
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"预处理器文件不存在: {file_path}")
                return False
            
            preprocessors = joblib.load(file_path)
            
            self.scalers = preprocessors.get('scalers', {})
            self.imputers = preprocessors.get('imputers', {})
            self.outlier_detectors = preprocessors.get('outlier_detectors', {})
            self.processing_history = preprocessors.get('processing_history', [])
            
            logger.info(f"预处理器已从 {file_path} 加载")
            return True
            
        except Exception as e:
            logger.error(f"加载预处理器失败: {e}")
            return False
    
    def get_preprocessing_statistics(self) -> Dict[str, Any]:
        """
        获取预处理统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'scalers_count': len(self.scalers),
            'imputers_count': len(self.imputers),
            'outlier_detectors_count': len(self.outlier_detectors),
            'operations_performed': len(self.processing_history),
            'output_directory': self.output_dir,
            'available_scalers': list(self.scalers.keys()),
            'available_imputers': list(self.imputers.keys()),
            'available_outlier_detectors': list(self.outlier_detectors.keys())
        }