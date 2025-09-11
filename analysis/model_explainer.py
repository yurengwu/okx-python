import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
import warnings
warnings.filterwarnings('ignore')

# SHAP相关导入
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP库未安装，部分功能将不可用")

# 机器学习相关导入
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler, LabelEncoder

class ModelExplainer:
    """模型解释性分析器
    
    提供SHAP值分析、特征重要性分析等模型解释功能
    """
    
    def __init__(self, model_dir: str = "models", output_dir: str = "explanations"):
        """
        初始化模型解释器
        
        Args:
            model_dir: 模型文件目录
            output_dir: 输出目录
        """
        self.model_dir = model_dir
        self.output_dir = output_dir
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 模型相关
        self.models = {}
        self.scalers = {}
        self.label_encoders = {}
        self.feature_columns = []
        
        # SHAP解释器
        self.shap_explainers = {}
        
        # 设置matplotlib中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        logger.info(f"模型解释器初始化完成，输出目录: {output_dir}")
    
    def load_models(self, model_type: str = 'ensemble') -> bool:
        """
        加载预训练模型
        
        Args:
            model_type: 模型类型 ('ensemble', 'single')
            
        Returns:
            是否加载成功
        """
        try:
            logger.info(f"加载模型用于解释分析，类型: {model_type}")
            
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
    
    def calculate_feature_importance(self, X: pd.DataFrame, y: pd.Series, 
                                   model_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        计算特征重要性
        
        Args:
            X: 特征数据
            y: 标签数据
            model_names: 要分析的模型名称列表
            
        Returns:
            特征重要性结果
        """
        try:
            logger.info("开始计算特征重要性...")
            
            if X.empty or y.empty:
                logger.error("输入数据为空")
                return {'success': False, 'error': '输入数据为空'}
            
            if model_names is None:
                model_names = list(self.models.keys())
            
            # 数据预处理
            scaler = self.scalers.get('ensemble') or list(self.scalers.values())[0]
            label_encoder = self.label_encoders.get('ensemble') or list(self.label_encoders.values())[0]
            
            # 处理分类特征
            categorical_features = ['hour_of_day', 'day_of_week', 'day_of_month']
            X_processed = X.copy()
            for feature in categorical_features:
                if feature in X_processed.columns:
                    X_processed[feature] = X_processed[feature].astype('category')
            
            # 确保特征列一致
            for col in self.feature_columns:
                if col not in X_processed.columns:
                    X_processed[col] = 0.0
            
            X_processed = X_processed[self.feature_columns]
            
            # 标准化和编码
            X_scaled = scaler.transform(X_processed)
            X_scaled = pd.DataFrame(X_scaled, columns=self.feature_columns)
            y_encoded = label_encoder.transform(y)
            
            importance_results = {}
            
            for model_name in model_names:
                if model_name not in self.models:
                    logger.warning(f"模型 {model_name} 不存在，跳过")
                    continue
                
                logger.info(f"计算 {model_name} 模型的特征重要性...")
                model = self.models[model_name]
                
                try:
                    # 内置特征重要性
                    builtin_importance = None
                    if hasattr(model, 'feature_importances_'):
                        builtin_importance = model.feature_importances_
                    elif hasattr(model, 'coef_'):
                        builtin_importance = np.abs(model.coef_[0]) if len(model.coef_.shape) > 1 else np.abs(model.coef_)
                    
                    # 排列重要性
                    perm_importance = permutation_importance(
                        model, X_scaled, y_encoded, 
                        n_repeats=10, random_state=42, n_jobs=-1
                    )
                    
                    importance_results[model_name] = {
                        'builtin_importance': builtin_importance.tolist() if builtin_importance is not None else None,
                        'permutation_importance_mean': perm_importance.importances_mean.tolist(),
                        'permutation_importance_std': perm_importance.importances_std.tolist(),
                        'feature_names': self.feature_columns
                    }
                    
                    logger.info(f"{model_name} 模型特征重要性计算完成")
                    
                except Exception as e:
                    logger.error(f"计算 {model_name} 模型特征重要性失败: {e}")
                    continue
            
            # 生成特征重要性图表
            self._plot_feature_importance(importance_results)
            
            # 保存结果
            result = {
                'success': True,
                'importance_results': importance_results,
                'feature_columns': self.feature_columns,
                'analysis_time': datetime.now().isoformat()
            }
            
            result_path = os.path.join(self.output_dir, 'feature_importance_results.pkl')
            joblib.dump(result, result_path)
            logger.info(f"特征重要性结果已保存到: {result_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"计算特征重要性失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def calculate_shap_values(self, X: pd.DataFrame, model_name: str = 'rf', 
                            sample_size: int = 100) -> Dict[str, Any]:
        """
        计算SHAP值
        
        Args:
            X: 特征数据
            model_name: 模型名称
            sample_size: 采样大小
            
        Returns:
            SHAP分析结果
        """
        if not SHAP_AVAILABLE:
            logger.error("SHAP库未安装，无法计算SHAP值")
            return {'success': False, 'error': 'SHAP库未安装'}
        
        try:
            logger.info(f"开始计算SHAP值，模型: {model_name}，样本数: {sample_size}")
            
            if X.empty:
                logger.error("输入数据为空")
                return {'success': False, 'error': '输入数据为空'}
            
            if model_name not in self.models:
                logger.error(f"模型 {model_name} 不存在")
                return {'success': False, 'error': f'模型 {model_name} 不存在'}
            
            # 数据预处理
            scaler = self.scalers.get('ensemble') or self.scalers.get(model_name) or list(self.scalers.values())[0]
            
            # 处理分类特征
            categorical_features = ['hour_of_day', 'day_of_week', 'day_of_month']
            X_processed = X.copy()
            for feature in categorical_features:
                if feature in X_processed.columns:
                    X_processed[feature] = X_processed[feature].astype('category')
            
            # 确保特征列一致
            for col in self.feature_columns:
                if col not in X_processed.columns:
                    X_processed[col] = 0.0
            
            X_processed = X_processed[self.feature_columns]
            
            # 标准化
            X_scaled = scaler.transform(X_processed)
            X_scaled = pd.DataFrame(X_scaled, columns=self.feature_columns)
            
            # 采样数据（SHAP计算可能很慢）
            if len(X_scaled) > sample_size:
                X_sample = X_scaled.sample(n=sample_size, random_state=42)
            else:
                X_sample = X_scaled
            
            model = self.models[model_name]
            
            # 创建SHAP解释器
            logger.info("创建SHAP解释器...")
            
            # 根据模型类型选择合适的解释器
            if model_name in ['rf', 'gb']:
                # 树模型使用TreeExplainer
                explainer = shap.TreeExplainer(model)
            elif model_name in ['xgb', 'lgb']:
                # XGBoost和LightGBM使用TreeExplainer
                explainer = shap.TreeExplainer(model)
            else:
                # 其他模型使用KernelExplainer（较慢但通用）
                background = shap.sample(X_scaled, 100)
                explainer = shap.KernelExplainer(model.predict_proba, background)
            
            self.shap_explainers[model_name] = explainer
            
            # 计算SHAP值
            logger.info("计算SHAP值...")
            shap_values = explainer.shap_values(X_sample)
            
            # 处理多类分类的情况
            if isinstance(shap_values, list):
                # 多类分类，取第一类的SHAP值
                shap_values_array = shap_values[0]
                logger.info(f"多类分类检测，使用第一类的SHAP值，共 {len(shap_values)} 类")
            else:
                shap_values_array = shap_values
            
            # 生成SHAP图表
            self._plot_shap_analysis(explainer, shap_values, X_sample, model_name)
            
            # 计算特征重要性（基于SHAP值）
            feature_importance = np.abs(shap_values_array).mean(axis=0)
            
            # 保存结果
            result = {
                'success': True,
                'model_name': model_name,
                'shap_values': shap_values_array.tolist(),
                'feature_importance': feature_importance.tolist(),
                'feature_names': self.feature_columns,
                'sample_size': len(X_sample),
                'analysis_time': datetime.now().isoformat()
            }
            
            result_path = os.path.join(self.output_dir, f'shap_results_{model_name}.pkl')
            joblib.dump(result, result_path)
            logger.info(f"SHAP分析结果已保存到: {result_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"计算SHAP值失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _plot_feature_importance(self, importance_results: Dict[str, Any]):
        """
        绘制特征重要性图表
        
        Args:
            importance_results: 特征重要性结果
        """
        try:
            logger.info("生成特征重要性图表...")
            
            n_models = len(importance_results)
            if n_models == 0:
                return
            
            fig, axes = plt.subplots(n_models, 2, figsize=(15, 5 * n_models))
            if n_models == 1:
                axes = axes.reshape(1, -1)
            
            for i, (model_name, results) in enumerate(importance_results.items()):
                feature_names = results['feature_names']
                
                # 内置特征重要性
                if results['builtin_importance'] is not None:
                    builtin_imp = np.array(results['builtin_importance'])
                    sorted_idx = np.argsort(builtin_imp)[-20:]  # 取前20个重要特征
                    
                    axes[i, 0].barh(range(len(sorted_idx)), builtin_imp[sorted_idx])
                    axes[i, 0].set_yticks(range(len(sorted_idx)))
                    axes[i, 0].set_yticklabels([feature_names[j] for j in sorted_idx])
                    axes[i, 0].set_title(f'{model_name.upper()} - 内置特征重要性')
                    axes[i, 0].set_xlabel('重要性')
                else:
                    axes[i, 0].text(0.5, 0.5, '无内置特征重要性', ha='center', va='center', transform=axes[i, 0].transAxes)
                    axes[i, 0].set_title(f'{model_name.upper()} - 内置特征重要性')
                
                # 排列重要性
                perm_imp = np.array(results['permutation_importance_mean'])
                perm_std = np.array(results['permutation_importance_std'])
                sorted_idx = np.argsort(perm_imp)[-20:]  # 取前20个重要特征
                
                axes[i, 1].barh(range(len(sorted_idx)), perm_imp[sorted_idx], 
                               xerr=perm_std[sorted_idx], capsize=3)
                axes[i, 1].set_yticks(range(len(sorted_idx)))
                axes[i, 1].set_yticklabels([feature_names[j] for j in sorted_idx])
                axes[i, 1].set_title(f'{model_name.upper()} - 排列重要性')
                axes[i, 1].set_xlabel('重要性')
            
            plt.tight_layout()
            
            # 保存图表
            plot_path = os.path.join(self.output_dir, 'feature_importance_plots.png')
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"特征重要性图表已保存到: {plot_path}")
            
        except Exception as e:
            logger.error(f"生成特征重要性图表失败: {e}")
    
    def _plot_shap_analysis(self, explainer, shap_values, X_sample: pd.DataFrame, model_name: str):
        """
        绘制SHAP分析图表
        
        Args:
            explainer: SHAP解释器
            shap_values: SHAP值
            X_sample: 样本数据
            model_name: 模型名称
        """
        if not SHAP_AVAILABLE:
            return
        
        try:
            logger.info(f"生成 {model_name} 模型的SHAP图表...")
            
            # 处理多类分类的情况
            if isinstance(shap_values, list):
                shap_values_plot = shap_values[0]
            else:
                shap_values_plot = shap_values
            
            # 1. SHAP摘要图
            plt.figure(figsize=(10, 8))
            shap.summary_plot(shap_values_plot, X_sample, feature_names=self.feature_columns, show=False)
            plt.title(f'{model_name.upper()} - SHAP摘要图')
            summary_path = os.path.join(self.output_dir, f'shap_summary_{model_name}.png')
            plt.savefig(summary_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 2. SHAP条形图
            plt.figure(figsize=(10, 8))
            shap.summary_plot(shap_values_plot, X_sample, feature_names=self.feature_columns, 
                            plot_type="bar", show=False)
            plt.title(f'{model_name.upper()} - SHAP特征重要性')
            bar_path = os.path.join(self.output_dir, f'shap_bar_{model_name}.png')
            plt.savefig(bar_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 3. SHAP瀑布图（单个样本）
            if len(X_sample) > 0:
                plt.figure(figsize=(10, 8))
                shap.waterfall_plot(explainer.expected_value[0] if isinstance(explainer.expected_value, np.ndarray) else explainer.expected_value,
                                  shap_values_plot[0], X_sample.iloc[0], feature_names=self.feature_columns, show=False)
                plt.title(f'{model_name.upper()} - SHAP瀑布图（样本1）')
                waterfall_path = os.path.join(self.output_dir, f'shap_waterfall_{model_name}.png')
                plt.savefig(waterfall_path, dpi=300, bbox_inches='tight')
                plt.close()
            
            logger.info(f"{model_name} 模型的SHAP图表生成完成")
            
        except Exception as e:
            logger.error(f"生成SHAP图表失败: {e}")
    
    def generate_explanation_report(self, X: pd.DataFrame, y: pd.Series, 
                                  model_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        生成完整的模型解释报告
        
        Args:
            X: 特征数据
            y: 标签数据
            model_names: 要分析的模型名称列表
            
        Returns:
            解释报告结果
        """
        try:
            logger.info("开始生成模型解释报告...")
            
            if model_names is None:
                model_names = list(self.models.keys())
            
            report = {
                'success': True,
                'analysis_time': datetime.now().isoformat(),
                'analyzed_models': model_names,
                'feature_count': len(self.feature_columns),
                'sample_count': len(X),
                'feature_importance': {},
                'shap_analysis': {},
                'summary': {}
            }
            
            # 1. 特征重要性分析
            logger.info("执行特征重要性分析...")
            importance_result = self.calculate_feature_importance(X, y, model_names)
            if importance_result['success']:
                report['feature_importance'] = importance_result['importance_results']
            
            # 2. SHAP分析（仅对部分模型）
            if SHAP_AVAILABLE:
                shap_models = [name for name in model_names if name in ['rf', 'gb', 'xgb', 'lgb']][:2]  # 限制分析的模型数量
                
                for model_name in shap_models:
                    logger.info(f"执行 {model_name} 模型的SHAP分析...")
                    shap_result = self.calculate_shap_values(X, model_name, sample_size=min(100, len(X)))
                    if shap_result['success']:
                        report['shap_analysis'][model_name] = {
                            'feature_importance': shap_result['feature_importance'],
                            'sample_size': shap_result['sample_size']
                        }
            
            # 3. 生成摘要
            report['summary'] = self._generate_summary(report)
            
            # 保存报告
            report_path = os.path.join(self.output_dir, 'explanation_report.pkl')
            joblib.dump(report, report_path)
            
            # 生成文本报告
            text_report_path = os.path.join(self.output_dir, 'explanation_report.txt')
            self._save_text_report(report, text_report_path)
            
            logger.info(f"模型解释报告生成完成，保存到: {report_path}")
            
            return report
            
        except Exception as e:
            logger.error(f"生成模型解释报告失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _generate_summary(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成分析摘要
        
        Args:
            report: 分析报告
            
        Returns:
            摘要信息
        """
        summary = {
            'top_features': {},
            'model_comparison': {},
            'recommendations': []
        }
        
        try:
            # 提取顶级特征
            if report['feature_importance']:
                all_features_importance = {}
                
                for model_name, results in report['feature_importance'].items():
                    if results['permutation_importance_mean']:
                        perm_imp = np.array(results['permutation_importance_mean'])
                        feature_names = results['feature_names']
                        
                        for i, importance in enumerate(perm_imp):
                            feature_name = feature_names[i]
                            if feature_name not in all_features_importance:
                                all_features_importance[feature_name] = []
                            all_features_importance[feature_name].append(importance)
                
                # 计算平均重要性
                avg_importance = {}
                for feature, importances in all_features_importance.items():
                    avg_importance[feature] = np.mean(importances)
                
                # 获取前10个重要特征
                top_features = sorted(avg_importance.items(), key=lambda x: x[1], reverse=True)[:10]
                summary['top_features'] = dict(top_features)
            
            # 模型比较
            if report['feature_importance']:
                model_scores = {}
                for model_name in report['feature_importance'].keys():
                    # 这里可以添加模型性能比较逻辑
                    model_scores[model_name] = 'analyzed'
                summary['model_comparison'] = model_scores
            
            # 生成建议
            recommendations = [
                "基于特征重要性分析，建议关注排名前5的特征",
                "考虑移除重要性极低的特征以简化模型",
                "定期重新评估特征重要性以适应数据变化"
            ]
            
            if SHAP_AVAILABLE and report['shap_analysis']:
                recommendations.append("SHAP分析提供了更详细的特征贡献解释")
            
            summary['recommendations'] = recommendations
            
        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
        
        return summary
    
    def _save_text_report(self, report: Dict[str, Any], file_path: str):
        """
        保存文本格式的报告
        
        Args:
            report: 分析报告
            file_path: 文件路径
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("模型解释性分析报告\n")
                f.write("=" * 50 + "\n\n")
                
                f.write(f"分析时间: {report['analysis_time']}\n")
                f.write(f"分析模型: {', '.join(report['analyzed_models'])}\n")
                f.write(f"特征数量: {report['feature_count']}\n")
                f.write(f"样本数量: {report['sample_count']}\n\n")
                
                # 顶级特征
                if report['summary']['top_features']:
                    f.write("重要特征排名:\n")
                    f.write("-" * 30 + "\n")
                    for i, (feature, importance) in enumerate(report['summary']['top_features'].items(), 1):
                        f.write(f"{i:2d}. {feature}: {importance:.4f}\n")
                    f.write("\n")
                
                # 建议
                if report['summary']['recommendations']:
                    f.write("分析建议:\n")
                    f.write("-" * 30 + "\n")
                    for i, rec in enumerate(report['summary']['recommendations'], 1):
                        f.write(f"{i}. {rec}\n")
                    f.write("\n")
                
                f.write("详细结果请查看对应的pkl文件和图表\n")
            
            logger.info(f"文本报告已保存到: {file_path}")
            
        except Exception as e:
            logger.error(f"保存文本报告失败: {e}")
    
    def get_model_statistics(self) -> Dict[str, Any]:
        """
        获取模型统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'loaded_models': list(self.models.keys()),
            'feature_count': len(self.feature_columns),
            'shap_available': SHAP_AVAILABLE,
            'output_directory': self.output_dir,
            'explainers_created': list(self.shap_explainers.keys())
        }