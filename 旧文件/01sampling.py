#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抽样脚本 - 01sampling.py

本脚本执行以下功能：
1. 搜索00_rawdata_dir，识别是否存在{APP_NAME}_sample为前缀的csv文件
2. 如果没有该命名模式的文件，建立{APP_NAME}_sample0.csv
3. 如果有该命名模式的文件，识别文件序号，增加一个新的序号文件
4. 从00_rawdata_dir中识别原始文件{APP_NAME}.csv，去掉已有样本数据
5. 按照用户输入的参数随机抽取N条数据
6. 抽样时可指定字符长度过滤
7. 基于data-management规范操作数据
"""

import os
import re
import pandas as pd
import random
from typing import List, Set, Optional
import logging

# 路径获取函数
from parameters import (
    get_path,
    APP_NAME
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_existing_sample_files(raw_data_dir: str) -> List[str]:
    """
    搜索原始数据目录中是否存在{APP_NAME}_sample为前缀的csv文件
    
    Args:
        raw_data_dir: 原始数据目录路径
        
    Returns:
        存在的样本文件名列表
    """
    sample_files = []
    if not os.path.exists(raw_data_dir):
        logger.warning(f"原始数据目录不存在: {raw_data_dir}")
        return sample_files
    
    # 构建样本文件前缀模式
    sample_pattern = re.compile(rf'^{re.escape(APP_NAME)}_sample\d+\.csv$')
    
    try:
        for filename in os.listdir(raw_data_dir):
            if sample_pattern.match(filename):
                sample_files.append(filename)
        
        # 按文件名排序确保序号顺序
        sample_files.sort()
        logger.info(f"找到 {len(sample_files)} 个现有样本文件: {sample_files}")
        
    except OSError as e:
        logger.error(f"读取目录时出错: {e}")
    
    return sample_files


def get_next_sample_filename(existing_files: List[str]) -> str:
    """
    根据现有样本文件确定下一个样本文件名
    
    Args:
        existing_files: 现有样本文件名列表
        
    Returns:
        下一个样本文件名
    """
    if not existing_files:
        return f"{APP_NAME}_sample0.csv"
    
    # 提取现有文件的序号
    numbers = []
    pattern = re.compile(rf'^{re.escape(APP_NAME)}_sample(\d+)\.csv$')
    
    for filename in existing_files:
        match = pattern.match(filename)
        if match:
            numbers.append(int(match.group(1)))
    
    # 获取最大序号并加一
    if numbers:
        next_number = max(numbers) + 1
    else:
        next_number = 0
    
    next_filename = f"{APP_NAME}_sample{next_number}.csv"
    logger.info(f"确定下一个样本文件名: {next_filename}")
    
    return next_filename


def get_existing_sample_ids(raw_data_dir: str, sample_files: List[str]) -> Set[str]:
    """
    获取所有现有样本文件中的用户ID集合
    
    Args:
        raw_data_dir: 原始数据目录路径
        sample_files: 样本文件名列表
        
    Returns:
        现有样本中所有用户ID的集合
    """
    existing_ids = set()
    
    for sample_file in sample_files:
        sample_path = os.path.join(raw_data_dir, sample_file)
        try:
            df = pd.read_csv(sample_path)
            if not df.empty and len(df.columns) >= 1:
                # 第一列为用户ID
                ids = df.iloc[:, 0].astype(str).tolist()
                existing_ids.update(ids)
                logger.info(f"从 {sample_file} 中读取了 {len(ids)} 个ID")
        except Exception as e:
            logger.error(f"读取样本文件 {sample_file} 时出错: {e}")
    
    logger.info(f"总计现有样本ID数量: {len(existing_ids)}")
    return existing_ids


def load_original_data(original_file_path: str) -> pd.DataFrame:
    """
    加载原始数据文件
    
    Args:
        original_file_path: 原始数据文件路径
        
    Returns:
        原始数据DataFrame
    """
    if not os.path.exists(original_file_path):
        raise FileNotFoundError(f"原始数据文件不存在: {original_file_path}")
    
    try:
        df = pd.read_csv(original_file_path)
        logger.info(f"成功加载原始数据，共 {len(df)} 行")
        return df
    except Exception as e:
        logger.error(f"加载原始数据时出错: {e}")
        raise


def filter_available_data(original_df: pd.DataFrame, existing_ids: Set[str], 
                         min_char_length: Optional[int] = None) -> pd.DataFrame:
    """
    过滤可用于抽样的数据
    
    Args:
        original_df: 原始数据DataFrame
        existing_ids: 已存在于样本中的ID集合
        min_char_length: 最小字符长度过滤条件
        
    Returns:
        过滤后的可用数据DataFrame
    """
    if original_df.empty:
        logger.warning("原始数据为空")
        return original_df
    
    # 确保有足够的列
    if len(original_df.columns) < 2:
        raise ValueError("原始数据应至少包含两列（用户ID和评论）")
    
    # 复制数据避免修改原始数据
    filtered_df = original_df.copy()
    
    # 转换第一列为字符串类型用于比较
    filtered_df.iloc[:, 0] = filtered_df.iloc[:, 0].astype(str)
    
    # 去除已存在于样本中的数据
    before_filter_count = len(filtered_df)
    filtered_df = filtered_df[~filtered_df.iloc[:, 0].isin(existing_ids)]
    after_filter_count = len(filtered_df)
    
    logger.info(f"去除重复ID后剩余数据: {after_filter_count} 行 (原有 {before_filter_count} 行)")
    
    # 如果指定了最小字符长度，过滤第二列
    if min_char_length is not None and min_char_length > 0:
        before_char_filter = len(filtered_df)
        filtered_df = filtered_df[filtered_df.iloc[:, 1].astype(str).str.len() >= min_char_length]
        after_char_filter = len(filtered_df)
        logger.info(f"应用字符长度过滤 (>= {min_char_length}) 后剩余数据: {after_char_filter} 行 (过滤前 {before_char_filter} 行)")
    
    return filtered_df


def sample_data(available_df: pd.DataFrame, sample_size: int) -> pd.DataFrame:
    """
    从可用数据中随机抽样
    
    Args:
        available_df: 可用数据DataFrame
        sample_size: 抽样数量
        
    Returns:
        抽样结果DataFrame
    """
    if available_df.empty:
        logger.warning("没有可用数据进行抽样")
        return pd.DataFrame()
    
    available_count = len(available_df)
    
    if sample_size > available_count:
        logger.warning(f"请求抽样数量 ({sample_size}) 超过可用数据量 ({available_count})，将抽取所有可用数据")
        sample_size = available_count
    
    # 随机抽样
    sampled_df = available_df.sample(n=sample_size, random_state=None).copy()
    logger.info(f"成功抽样 {len(sampled_df)} 条数据")
    
    return sampled_df


def save_sample_data(sample_df: pd.DataFrame, output_path: str) -> bool:
    """
    保存抽样数据到文件
    
    Args:
        sample_df: 抽样数据DataFrame
        output_path: 输出文件路径
        
    Returns:
        保存是否成功
    """
    if sample_df.empty:
        logger.warning("抽样数据为空，不保存文件")
        return False
    
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 保存数据
        sample_df.to_csv(output_path, index=False, encoding='utf-8')
        logger.info(f"成功保存抽样数据到: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"保存抽样数据时出错: {e}")
        return False


def sample_data_programmatic(sample_size: int, min_length: Optional[int] = None) -> dict:
    """
    程序化抽样接口 - 可在程序中直接调用
    
    Args:
        sample_size: 抽样数量
        min_length: 最小字符长度过滤条件（可选）
        
    Returns:
        dict: 包含抽样结果的字典
        {
            'success': bool,           # 是否成功
            'sample_file': str,        # 新样本文件名
            'sample_count': int,       # 实际抽样数量
            'sample_data': pd.DataFrame, # 抽样数据（可选）
            'message': str             # 结果消息
        }
    """
    try:
        # 获取路径配置
        raw_data_dir = get_path('UR_path')
        original_file_path = get_path('UR')
        
        logger.info(f"开始程序化抽样流程 - APP_NAME: {APP_NAME}")
        logger.info(f"原始数据目录: {raw_data_dir}")
        logger.info(f"原始数据文件: {original_file_path}")
        logger.info(f"抽样数量: {sample_size}")
        if min_length:
            logger.info(f"最小字符长度: {min_length}")
        
        # 1. 搜索现有样本文件
        existing_sample_files = find_existing_sample_files(raw_data_dir)
        
        # 2. 确定新样本文件名
        new_sample_filename = get_next_sample_filename(existing_sample_files)
        new_sample_path = os.path.join(raw_data_dir, new_sample_filename)
        
        # 3. 获取现有样本中的ID
        existing_ids = get_existing_sample_ids(raw_data_dir, existing_sample_files)
        
        # 4. 加载原始数据
        original_df = load_original_data(original_file_path)
        
        # 5. 过滤可用数据
        available_df = filter_available_data(original_df, existing_ids, min_length)
        
        if available_df.empty:
            message = "没有可用数据进行抽样"
            logger.error(message)
            return {
                'success': False,
                'sample_file': '',
                'sample_count': 0,
                'sample_data': pd.DataFrame(),
                'message': message
            }
        
        # 6. 进行抽样
        sample_df = sample_data(available_df, sample_size)
        
        if sample_df.empty:
            message = "抽样失败"
            logger.error(message)
            return {
                'success': False,
                'sample_file': '',
                'sample_count': 0,
                'sample_data': pd.DataFrame(),
                'message': message
            }
        
        # 7. 保存抽样结果
        success = save_sample_data(sample_df, new_sample_path)
        
        if success:
            message = f"抽样流程完成成功！新样本文件: {new_sample_filename}, 抽样数量: {len(sample_df)}"
            logger.info(message)
            return {
                'success': True,
                'sample_file': new_sample_filename,
                'sample_count': len(sample_df),
                'sample_data': sample_df.copy(),
                'message': message
            }
        else:
            message = "保存抽样结果失败"
            logger.error(message)
            return {
                'success': False,
                'sample_file': new_sample_filename,
                'sample_count': len(sample_df),
                'sample_data': sample_df.copy(),
                'message': message
            }
            
    except Exception as e:
        message = f"抽样流程出现异常: {e}"
        logger.error(message)
        return {
            'success': False,
            'sample_file': '',
            'sample_count': 0,
            'sample_data': pd.DataFrame(),
            'message': message
        }


def main(sample_size, min_length):
    """主函数 - 直接在IDE中运行"""
    
    print("=" * 50)
    print("金铲铲数据抽样")
    print("=" * 50)
    print(f"APP_NAME: {APP_NAME}")
    print(f"抽样数量: {sample_size}")
    if min_length:
        print(f"最小字符长度: {min_length}")
    print("-" * 50)
    
    # 执行抽样
    result = sample_data_programmatic(sample_size, min_length)
    
    # 显示结果
    if result['success']:
        print("✅ 抽样成功完成！")
        print(f"   样本文件: {result['sample_file']}")
        print(f"   抽样数量: {result['sample_count']}")
        print(f"   消息: {result['message']}")
        
        # 显示样本数据预览
        sample_df = result['sample_data']
        if not sample_df.empty:
            print(f"\n📋 样本数据预览（前3条）:")
            print(sample_df.head(3).to_string(index=False, max_colwidth=50))
            
            # 如果有字符长度过滤，显示统计
            if min_length:
                lengths = sample_df.iloc[:, 1].astype(str).str.len()
                print(f"\n📊 评论长度统计:")
                print(f"   最短: {lengths.min()} 字符")
                print(f"   最长: {lengths.max()} 字符") 
                print(f"   平均: {lengths.mean():.1f} 字符")
        
    else:
        print("❌ 抽样失败")
        print(f"   错误信息: {result['message']}")
    
    print("=" * 50)
    return result['success']


if __name__ == "__main__":

    # ==================== 配置参数 ====================
    # 在这里修改抽样参数
    SAMPLE_SIZE = 100        # 抽样数量
    MIN_LENGTH = 40        # 最小字符长度过滤（None表示不过滤）
    # ================================================
    success = main(SAMPLE_SIZE, MIN_LENGTH)
    if success:
        print("程序执行完成")
    else:
        print("程序执行失败") 