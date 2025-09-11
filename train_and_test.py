#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票预测模型训练和测试脚本

该脚本用于训练和测试股票预测模型，包括：
1. 数据准备和特征工程
2. 模型训练（随机森林、梯度提升、XGBoost、LightGBM）
3. 超参数优化
4. 模型验证和评估
5. 集成模型训练
6. 实时预测测试
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
import warnings
warnings.filterwarnings('ignore')

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analysis.prediction_model import TradingPredictionModel
from analysis.model_explainer import ModelExplainer
from analysis.real_time_predictor import RealTimePredictor
from preprocessing.advanced_preprocessor import AdvancedDataPreprocessor
from core.database import TradingDatabase

def setup_logging():
    """设置日志配置"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "logs/training_{time}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB"
    )

def check_data_availability():
    """检查数据可用性"""
    logger.info("检查数据可用性...")
    
    try:
        db = TradingDatabase()
        
        # 检查K线数据 - 使用实际存在的方法
        # 尝试获取数据来检查数据量
        test_data = db.get_kline_data('BTCUSDT', '1h', 2000)  # 尝试获取更多数据来检查总量
        
        if test_data is None or test_data.empty:
            logger.warning("没有找到K线数据，可能需要先收集数据")
            # 尝试其他常见的交易对
            for symbol in ['ETHUSDT', 'BNBUSDT', 'ADAUSDT']:
                test_data = db.get_kline_data(symbol, '1h', 2000)
                if test_data is not None and not test_data.empty:
                    logger.info(f"找到 {symbol} 的数据，数据量: {len(test_data)}")
                    break
            
            if test_data is None or test_data.empty:
                logger.error("没有找到任何K线数据，请先运行数据收集程序")
                return False
        
        kline_count = len(test_data)
        logger.info(f"K线数据总数: {kline_count}")
        
        if kline_count < 100:
            logger.warning(f"K线数据量较少 ({kline_count})，建议至少有100条数据用于训练")
            return False
        
        # 检查最新数据时间
        latest_time = db.get_latest_timestamp('BTCUSDT', '1h')
        if latest_time:
            time_diff = datetime.now() - latest_time
            logger.info(f"最新数据时间: {latest_time}, 距现在: {time_diff}")
            
            if time_diff > timedelta(days=30):
                logger.warning("数据可能过时，建议更新数据")
        else:
            logger.warning("无法获取最新数据时间")
        
        return True
        
    except Exception as e:
        logger.error(f"检查数据可用性失败: {e}")
        return False

def train_basic_models():
    """训练基础模型"""
    logger.info("=" * 60)
    logger.info("开始训练基础模型...")
    logger.info("=" * 60)
    
    try:
        # 初始化预测模型
        model = TradingPredictionModel()
        
        # 准备训练数据
        logger.info("准备训练数据...")
        X, y = model.prepare_training_data(days=365)
        
        if X.empty or y.empty:
            logger.error("训练数据为空，无法进行训练")
            return False
        
        logger.info(f"训练数据形状: X={X.shape}, y={y.shape}")
        logger.info(f"标签分布: {y.value_counts().to_dict()}")
        
        # 训练模型
        logger.info("开始训练模型...")
        results = model.train_models(X, y)
        
        # 显示训练结果
        logger.info("训练结果:")
        for model_name, metrics in results.items():
            logger.info(f"  {model_name}:")
            for metric, value in metrics.items():
                logger.info(f"    {metric}: {value:.4f}")
        
        # 保存模型
        if model.save_models():
            logger.info("模型保存成功")
        else:
            logger.error("模型保存失败")
            return False
        
        # 获取特征重要性
        logger.info("分析特征重要性...")
        feature_importance = model.get_feature_importance()
        
        logger.info("特征重要性排名（前10）:")
        sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        for feature, importance in sorted_features:
            logger.info(f"  {feature}: {importance:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"训练基础模型失败: {e}")
        return False

def optimize_hyperparameters():
    """超参数优化"""
    logger.info("=" * 60)
    logger.info("开始超参数优化...")
    logger.info("=" * 60)
    
    try:
        model = TradingPredictionModel()
        
        # 准备数据
        X, y = model.prepare_training_data(days=365)
        
        if X.empty or y.empty:
            logger.error("训练数据为空，无法进行超参数优化")
            return False
        
        # 执行超参数优化
        logger.info("执行网格搜索优化...")
        grid_results = model.optimize_hyperparameters(X, y, method='grid_search')
        
        if grid_results['success']:
            logger.info("网格搜索优化完成")
            logger.info(f"最佳参数: {grid_results['best_params']}")
            logger.info(f"最佳得分: {grid_results['best_score']:.4f}")
        
        # 使用优化参数训练模型
        logger.info("使用优化参数训练模型...")
        optimized_results = model.train_models_with_optimized_params(X, y)
        
        if optimized_results['success']:
            logger.info("优化模型训练完成")
            for model_name, metrics in optimized_results['results'].items():
                logger.info(f"  {model_name} 优化后性能:")
                for metric, value in metrics.items():
                    logger.info(f"    {metric}: {value:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"超参数优化失败: {e}")
        return False

def validate_models():
    """模型验证"""
    logger.info("=" * 60)
    logger.info("开始模型验证...")
    logger.info("=" * 60)
    
    try:
        model = TradingPredictionModel()
        
        # 准备数据
        X, y = model.prepare_training_data(days=365)
        
        if X.empty or y.empty:
            logger.error("训练数据为空，无法进行模型验证")
            return False
        
        # 时间序列交叉验证
        logger.info("执行时间序列交叉验证...")
        cv_results = model.time_series_cross_validation(X, y, n_splits=5)
        
        if cv_results['success']:
            logger.info("时间序列交叉验证完成")
            logger.info(f"平均准确率: {cv_results['mean_accuracy']:.4f} ± {cv_results['std_accuracy']:.4f}")
            logger.info(f"平均F1分数: {cv_results['mean_f1']:.4f} ± {cv_results['std_f1']:.4f}")
        
        # 滑动窗口验证
        logger.info("执行滑动窗口验证...")
        walk_results = model.walk_forward_validation(X, y, window_size=200, step_size=50)
        
        if walk_results['success']:
            logger.info("滑动窗口验证完成")
            logger.info(f"平均准确率: {walk_results['mean_accuracy']:.4f}")
            logger.info(f"平均F1分数: {walk_results['mean_f1']:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"模型验证失败: {e}")
        return False

def train_ensemble_models():
    """训练集成模型"""
    logger.info("=" * 60)
    logger.info("开始训练集成模型...")
    logger.info("=" * 60)
    
    try:
        model = TradingPredictionModel()
        
        # 准备数据
        X, y = model.prepare_training_data(days=365)
        
        if X.empty or y.empty:
            logger.error("训练数据为空，无法训练集成模型")
            return False
        
        # 创建集成模型
        logger.info("创建和训练集成模型...")
        ensemble_results = model.create_ensemble_models(X, y)
        
        if ensemble_results['success']:
            logger.info("集成模型训练完成")
            
            # 显示投票分类器结果
            if 'voting_classifier' in ensemble_results['results']:
                voting_metrics = ensemble_results['results']['voting_classifier']
                logger.info("投票分类器性能:")
                for metric, value in voting_metrics.items():
                    logger.info(f"  {metric}: {value:.4f}")
            
            # 显示堆叠集成结果
            if 'stacking_classifier' in ensemble_results['results']:
                stacking_metrics = ensemble_results['results']['stacking_classifier']
                logger.info("堆叠集成性能:")
                for metric, value in stacking_metrics.items():
                    logger.info(f"  {metric}: {value:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"训练集成模型失败: {e}")
        return False

def analyze_model_explainability():
    """模型解释性分析"""
    logger.info("=" * 60)
    logger.info("开始模型解释性分析...")
    logger.info("=" * 60)
    
    try:
        # 初始化模型解释器
        explainer = ModelExplainer()
        
        # 加载模型
        if not explainer.load_models('single'):
            logger.error("无法加载模型进行解释性分析")
            return False
        
        # 准备数据
        model = TradingPredictionModel()
        X, y = model.prepare_training_data(days=365)
        
        if X.empty or y.empty:
            logger.error("训练数据为空，无法进行解释性分析")
            return False
        
        # 生成解释报告
        logger.info("生成模型解释报告...")
        report = explainer.generate_explanation_report(X, y)
        
        if report['success']:
            logger.info("模型解释报告生成完成")
            
            # 显示重要特征
            if 'summary' in report and 'top_features' in report['summary']:
                logger.info("重要特征排名（前5）:")
                top_features = list(report['summary']['top_features'].items())[:5]
                for feature, importance in top_features:
                    logger.info(f"  {feature}: {importance:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"模型解释性分析失败: {e}")
        return False

def test_real_time_prediction():
    """测试实时预测功能"""
    logger.info("=" * 60)
    logger.info("开始测试实时预测功能...")
    logger.info("=" * 60)
    
    try:
        # 初始化实时预测器
        predictor = RealTimePredictor()
        
        # 加载模型
        if not predictor.load_models():
            logger.error("无法加载模型进行实时预测测试")
            return False
        
        # 准备测试数据
        model = TradingPredictionModel()
        X, y = model.prepare_training_data(days=30)  # 使用最近30天的数据进行测试
        
        if X.empty:
            logger.error("测试数据为空，无法进行实时预测测试")
            return False
        
        # 测试批量预测
        logger.info("测试批量预测...")
        batch_results = predictor.predict_batch(X.head(10))  # 测试前10条数据
        
        if batch_results['success']:
            logger.info(f"批量预测完成，预测了 {len(batch_results['predictions'])} 个样本")
            logger.info(f"预测结果: {batch_results['predictions'][:5]}...")  # 显示前5个结果
        
        # 测试单次预测
        logger.info("测试单次预测...")
        single_data = X.iloc[0].to_dict()
        single_result = predictor.predict_single(single_data)
        
        if single_result['success']:
            logger.info(f"单次预测完成: {single_result['prediction']}")
            logger.info(f"预测概率: {single_result.get('probability', 'N/A')}")
        
        # 显示性能统计
        stats = predictor.get_performance_stats()
        logger.info("实时预测性能统计:")
        logger.info(f"  总预测次数: {stats['total_predictions']}")
        logger.info(f"  平均预测时间: {stats['average_prediction_time']:.4f}秒")
        
        return True
        
    except Exception as e:
        logger.error(f"实时预测测试失败: {e}")
        return False

def test_data_preprocessing():
    """测试数据预处理功能"""
    logger.info("=" * 60)
    logger.info("开始测试数据预处理功能...")
    logger.info("=" * 60)
    
    try:
        # 初始化预处理器
        preprocessor = AdvancedDataPreprocessor()
        
        # 准备测试数据
        model = TradingPredictionModel()
        X, y = model.prepare_training_data(days=365)
        
        if X.empty:
            logger.error("测试数据为空，无法进行预处理测试")
            return False
        
        # 异常值检测
        logger.info("执行异常值检测...")
        outlier_results = preprocessor.detect_outliers(X, methods=['isolation_forest', 'z_score', 'iqr'])
        
        if outlier_results['success']:
            logger.info("异常值检测完成")
            for method, result in outlier_results['outlier_results'].items():
                logger.info(f"  {method}: 检测到 {result['outlier_count']} 个异常值 ({result['outlier_percentage']:.2f}%)")
        
        # 缺失值处理
        logger.info("执行缺失值处理...")
        processed_data = preprocessor.handle_missing_values(X, strategy='advanced')
        logger.info(f"缺失值处理完成，数据形状: {processed_data.shape}")
        
        # 特征缩放
        logger.info("执行特征缩放...")
        scaled_data, scaler = preprocessor.scale_features(processed_data, method='robust')
        logger.info(f"特征缩放完成，使用方法: robust")
        
        # 生成预处理报告
        logger.info("生成预处理报告...")
        report = preprocessor.generate_preprocessing_report(X, scaled_data)
        
        if report['success']:
            logger.info("预处理报告生成完成")
            logger.info(f"数据形状变化: {report['data_summary']['original_shape']} -> {report['data_summary']['processed_shape']}")
        
        return True
        
    except Exception as e:
        logger.error(f"数据预处理测试失败: {e}")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 80)
    print("🚀 股票预测系统训练和测试")
    print("=" * 80)
    
    # 设置日志
    setup_logging()
    
    # 创建必要的目录
    os.makedirs("logs", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    os.makedirs("explanations", exist_ok=True)
    os.makedirs("preprocessing_results", exist_ok=True)
    
    # 检查数据可用性
    if not check_data_availability():
        logger.error("数据检查失败，请确保有足够的历史数据")
        return
    
    success_count = 0
    total_tests = 7
    
    # 1. 训练基础模型
    if train_basic_models():
        success_count += 1
        logger.info("✅ 基础模型训练成功")
    else:
        logger.error("❌ 基础模型训练失败")
    
    # 2. 超参数优化
    if optimize_hyperparameters():
        success_count += 1
        logger.info("✅ 超参数优化成功")
    else:
        logger.error("❌ 超参数优化失败")
    
    # 3. 模型验证
    if validate_models():
        success_count += 1
        logger.info("✅ 模型验证成功")
    else:
        logger.error("❌ 模型验证失败")
    
    # 4. 集成模型训练
    if train_ensemble_models():
        success_count += 1
        logger.info("✅ 集成模型训练成功")
    else:
        logger.error("❌ 集成模型训练失败")
    
    # 5. 模型解释性分析
    if analyze_model_explainability():
        success_count += 1
        logger.info("✅ 模型解释性分析成功")
    else:
        logger.error("❌ 模型解释性分析失败")
    
    # 6. 实时预测测试
    if test_real_time_prediction():
        success_count += 1
        logger.info("✅ 实时预测测试成功")
    else:
        logger.error("❌ 实时预测测试失败")
    
    # 7. 数据预处理测试
    if test_data_preprocessing():
        success_count += 1
        logger.info("✅ 数据预处理测试成功")
    else:
        logger.error("❌ 数据预处理测试失败")
    
    # 总结
    print("\n" + "=" * 80)
    print("📊 训练和测试总结")
    print("=" * 80)
    logger.info(f"成功完成: {success_count}/{total_tests} 个测试")
    logger.info(f"成功率: {success_count/total_tests*100:.1f}%")
    
    if success_count == total_tests:
        logger.info("🎉 所有测试都成功完成！系统已准备就绪。")
    elif success_count >= total_tests * 0.7:
        logger.info("⚠️  大部分测试成功，系统基本可用，但建议检查失败的部分。")
    else:
        logger.error("❌ 多个测试失败，请检查系统配置和数据。")
    
    print("=" * 80)

if __name__ == "__main__":
    main()