# parameters.py
"""
项目参数管理模块

本模块分为以下几个主要区域：

1. 公开接口 (Public Interfaces)
   - 全局变量
   - 公开函数
   - 数据类型定义

2. 内部实现 (Internal Implementation)
   - 内部辅助函数
   - 内部数据结构
   - 工具类实现

=== 公开接口说明 ===

全局变量:
- PROJECT_ROOT: str
    项目根目录的绝对路径
- APP_NAME: str
    当前应用名称，默认为 'myworld'

公开函数:
1. 路径管理:
- get_path(key: str) -> str
    获取单个文件或目录的路径
    参数:
        key: 路径键名（如 'UR', 'UR_id', 'APP_PATH' 等）
    返回:
        对应的文件或目录的完整路径

2. 项目管理:
- setup_project(mode: str = "setup") -> bool
    项目初始化设置
    参数:
        mode: "setup" 或 "reset"
    返回:
        设置是否成功

=== 内部实现说明 ===

以下划线开头的函数和变量为内部实现，不建议外部直接调用：
- _ensure_file_dir_initialized()
- _build_project_file_dir_internal()
- _PROJECT_FILE_DIR

"""

import os
import re   # For sanitize_folder_name
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any, Set, Callable
import shutil # For file operations
import sys    # For command line arguments
from datetime import datetime
from dataclasses import dataclass
import pandas as pd
import logging  # 替换外部logger导入

# 配置内置logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('workflow.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===================== 公开接口 (Public Interfaces) =====================

# --- 全局变量 ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR_BASE_NAME = "data_dir"
APP_NAME = '金铲铲'

# --- 调试配置 ---
P_DBUG_RESPONDENT_ID = 10  # 调试目标受访者ID
P_DBUG_QUESTION_TEXT_RAW = 7  # 调试目标问题文本

# --- 常量定义 ---
# 各阶段子目录的固定名称
SDIR_00_RAW = "00_rawdata_dir"
SDIR_01_INDUCTIVE = "01_inductive_coding_dir"
SDIR_02_DEDUCTIVE = "02_deductive_coding_dir"

# --- 公开函数 ---
def get_path(key: str) -> str:
    """获取单个文件或目录的路径"""
    global _PROJECT_FILE_DIR
    _ensure_file_dir_initialized()
    if _PROJECT_FILE_DIR is None or not isinstance(_PROJECT_FILE_DIR, dict):
        raise RuntimeError("项目路径配置 _PROJECT_FILE_DIR 未能成功初始化或类型不正确。")
        
    path_value = _PROJECT_FILE_DIR.get(key)
    if path_value is None:
        raise KeyError(f"路径键 '{key}' 在项目路径配置中未找到。可用键示例: 'APP_PATH', 'UR'等。")
    if not isinstance(path_value, str):
        raise TypeError(f"路径键 '{key}' 期望获取字符串路径，但得到的是类型 {type(path_value)}。请使用 get_path_list 获取列表型路径，或检查键名是否正确。")
    return path_value

def get_path_list(key: str) -> List[Any]:
    """获取路径列表（如按分类分组的文件路径列表）"""
    global _PROJECT_FILE_DIR
    _ensure_file_dir_initialized()
    if _PROJECT_FILE_DIR is None or not isinstance(_PROJECT_FILE_DIR, dict):
        raise RuntimeError("项目路径配置 _PROJECT_FILE_DIR 未能成功初始化或类型不正确。")

    path_value = _PROJECT_FILE_DIR.get(key)
    if path_value is None:
        raise KeyError(f"路径列表键 '{key}' 在项目路径配置中未找到。可用键示例: 'UR_samples'等。")
    if not isinstance(path_value, list):
        raise TypeError(f"路径列表键 '{key}' 期望获取列表，但得到的是类型 {type(path_value)}。请使用 get_path 获取单一字符串路径，或检查键名是否正确。")
    return path_value

# ===================== 内部实现 (Internal Implementation) =====================

# --- 内部变量 ---
_PROJECT_FILE_DIR: Optional[Dict[str, Any]] = None

# --- 内部函数 ---
def sanitize_folder_name(name: str) -> str:
    """确保文件夹名称在所有操作系统上都有效，移除或替换非法字符。"""
    invalid_chars_pattern = r'[<>:"/\\|?*\x00-\x1F]' 
    safe_name = re.sub(invalid_chars_pattern, '_', name)
    safe_name = re.sub(r'_+', '_', safe_name)
    safe_name = safe_name.strip('_.')
    if not safe_name: # Handle cases where the name becomes empty after sanitization
        safe_name = "sanitized_folder_name" 
    return safe_name

def validate_file_dir(file_dir: Dict[str, str]) -> bool:
    """验证 file_dir 中的关键路径是否都已正确设置"""
    required_keys = ['APP_PATH', 'UR']
    return all(key in file_dir and isinstance(file_dir[key], str) for key in required_keys)

def _build_project_file_dir_internal(
    base_data_dir_for_app_folders: str,
    current_app_name: str
) -> Dict[str, Any]:
    """
    (内部辅助函数) 根据给定的基础路径和应用名称，
    构建项目的文件/目录路径配置字典 (file_dir)。

    Args:
        base_data_dir_for_app_folders (str): 存放所有应用特定数据文件夹的基础目录路径。
        current_app_name (str): 当前正在处理的应用/项目名称。

    Returns:
        Dict[str, Any]: file_dir 字典，包含路径字符串、路径列表或文件名模式。
    """
    if not base_data_dir_for_app_folders or not current_app_name:
        raise ValueError("构建路径配置：基础数据目录或应用名称不能为空。")

    file_dir: Dict[str, Any] = {}
    app_folder_name = f"{current_app_name}_dir" # 例如 myworld_dir
    current_app_path = os.path.join(base_data_dir_for_app_folders, app_folder_name)

    file_dir['APP_PATH'] = os.path.join(current_app_path, '')

    # --- 固定路径填充 ---
    raw_data_dir = os.path.join(current_app_path, SDIR_00_RAW)
    file_dir['UR_path'] = os.path.join(raw_data_dir, '') # 目录路径
    
    inductive_dir = os.path.join(current_app_path, SDIR_01_INDUCTIVE)
    file_dir['inductive_global_dir'] = os.path.join(inductive_dir, '') # 目录路径

    deductive_dir = os.path.join(current_app_path, SDIR_02_DEDUCTIVE)
    file_dir['deductive_global_dir'] = os.path.join(deductive_dir, '') # 目录路径

    # --- 文件名模式 ---
    file_dir['UR'] = os.path.join(raw_data_dir, f"{current_app_name}.csv")


    return file_dir

def get_project_paths(base_dir_for_apps: str, app_name: str) -> Dict[str, Any]:
    """
    获取项目的所有路径配置。

    Args:
        base_dir_for_apps (str): 存放所有应用特定数据文件夹的基础目录路径。
        app_name (str): 当前应用的名称。

    Returns:
        Dict[str, Any]: 项目路径配置字典
    """
    file_dir = _build_project_file_dir_internal(base_dir_for_apps, app_name)
    return file_dir

def _ensure_file_dir_initialized() -> None:
    """确保 _PROJECT_FILE_DIR 已初始化"""
    global _PROJECT_FILE_DIR
    if _PROJECT_FILE_DIR is None:
        # 构建正确的数据目录路径，包含data_dir
        data_dir_path = os.path.join(PROJECT_ROOT, DATA_DIR_BASE_NAME)
        _PROJECT_FILE_DIR = get_project_paths(data_dir_path, APP_NAME)

def create_project_dir(target_file_dir: Dict[str, Any]) -> bool:
    """
    创建项目所需的目录结构。

    Args:
        target_file_dir (Dict[str, Any]): 包含所有必要路径的字典。

    Returns:
        bool: 如果所有目录都成功创建，则返回 True。
    """
    if not target_file_dir:
        logger.error("目标文件目录配置为空")
        return False

    try:
        # 创建所有必要的目录
        for key, path in target_file_dir.items():
            if isinstance(path, str) and path.endswith(os.sep):
                os.makedirs(path, exist_ok=True)
                logger.info(f"创建目录: {path}")

        return True
    except Exception as e:
        logger.error(f"创建项目目录时发生错误: {e}")
        return False

def move_original_data(
    source_project_root: str,
    target_file_dir: Dict[str, str],
    app_name: str
) -> bool:
    """
    将原始数据文件从源项目移动到目标项目。
    
    参数:
        source_project_root: 源项目根目录
        target_file_dir: 目标项目的文件目录配置
        app_name: 应用名称
    
    返回:
        bool: 操作是否成功
    """
    if not source_project_root or not target_file_dir or not app_name:
        logger.error("源项目根目录、目标文件目录配置或应用名称不能为空")
        return False
        
    source_data_filename = f"{app_name}.csv"
    source_data_filepath = os.path.join(source_project_root, source_data_filename)
    
    if not os.path.exists(source_data_filepath):
        logger.error(f"源数据文件不存在: {source_data_filepath}")
        return False
    
    dest_data_filepath = target_file_dir.get('UR')
    if not dest_data_filepath:
        logger.warning("目标路径 'UR' 在 file_dir 中未定义")
        return False

    try:
        # 确保目标目录存在
        dest_dir = os.path.dirname(dest_data_filepath)
        os.makedirs(dest_dir, exist_ok=True)
        logger.info(f"确保目标目录存在: {dest_dir}")
        
        # 检查目标文件是否已存在
        if os.path.exists(dest_data_filepath):
            logger.warning(f"目标文件已存在，将被覆盖: {dest_data_filepath}")
        
        # 移动数据文件
        shutil.copy2(source_data_filepath, dest_data_filepath)
        logger.info(f"成功将数据文件从 {source_data_filepath} 复制到 {dest_data_filepath}")
        
        return True
    except PermissionError as e:
        logger.error(f"权限错误，无法访问文件: {e}")
        return False
    except OSError as e:
        logger.error(f"操作系统错误: {e}")
        return False
    except Exception as e:
        logger.error(f"移动数据文件时发生未知错误: {e}")
        return False

def move_original_data_back(
    source_file_dir: Dict[str, str],
    app_name: str
) -> bool:
    """
    将原始数据文件从项目目录移回原始位置。
    
    参数:
        source_file_dir: 源项目的文件目录配置
        app_name: 应用名称
    
    返回:
        bool: 操作是否成功
    """
    if not source_file_dir or not app_name:
        logger.error("源文件目录配置或应用名称不能为空")
        return False
        
    source_data_filepath = source_file_dir.get('UR')
    if not source_data_filepath:
        logger.error("源路径 'UR' 在 file_dir 中未定义。无法执行移回操作。")
        return False
        
    if not os.path.exists(source_data_filepath):
        logger.error(f"源数据文件不存在: {source_data_filepath}")
        return False

    # 构建目标路径：从源文件路径向上两级目录
    source_dir = os.path.dirname(source_data_filepath)  # 获取源文件所在目录
    project_dir = os.path.dirname(source_dir)  # 获取项目目录
    dest_data_filename = f"{app_name}.csv"
    dest_data_filepath = os.path.join(project_dir, dest_data_filename)

    try:
        # 确保目标目录存在
        dest_dir = os.path.dirname(dest_data_filepath)
        os.makedirs(dest_dir, exist_ok=True)
        logger.info(f"确保目标目录存在: {dest_dir}")
        
        # 检查目标文件是否已存在
        if os.path.exists(dest_data_filepath):
            logger.warning(f"目标文件已存在，将被覆盖: {dest_data_filepath}")
        
        # 移动数据文件
        shutil.copy2(source_data_filepath, dest_data_filepath)
        logger.info(f"成功将数据文件从 {source_data_filepath} 复制到 {dest_data_filepath}")
        
        return True
    except PermissionError as e:
        logger.error(f"权限错误，无法访问文件: {e}")
        return False
    except OSError as e:
        logger.error(f"操作系统错误: {e}")
        return False
    except Exception as e:
        logger.error(f"移回数据文件时发生未知错误: {e}")
        return False

def process_raw_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    处理DataFrame中的多行文本，特别处理第二列数据。

    Args:
        raw_df (pd.DataFrame): 原始数据DataFrame

    Returns:
        pd.DataFrame: 处理后的DataFrame
    """
    # 创建一个新的DataFrame来存储处理后的数据
    processed_df = raw_df.copy()
    
    # 对每一列进行处理
    replacements = {
            '\n': ' ', '\r': ' ', '\\n': ' ', '\\r': ' ',
            '\t': ' ', '\\t': ' '
        }
        
    # 对所有文本列应用清理
    for col in processed_df.columns:
        if processed_df[col].dtype == 'object':  # 只处理文本列
            processed_df[col] = processed_df[col].astype(str).replace(replacements, regex=True)
            # 移除多余的空格
            processed_df[col] = processed_df[col].str.strip()
    
    # 特别处理第二列
    if len(processed_df.columns) >= 2:
        second_col = processed_df.columns[1]
        # 确保第二列是字符串类型
        processed_df[second_col] = processed_df[second_col].astype(str)
        # 移除所有HTML标签
        processed_df[second_col] = processed_df[second_col].str.replace(r'<[^>]+>', '', regex=True)
        # 移除多余的空格和换行符
        processed_df[second_col] = processed_df[second_col].str.replace(r'\s+', ' ', regex=True).str.strip()
    
    return processed_df

def validate_workflow_config(
    mode: str,
    base_dir_for_apps: str,
    app_to_manage: str,
    initial_files_source_root: str
) -> Tuple[bool, str]:
    """
    验证工作流配置参数
    
    Args:
        mode (str): 操作模式
        base_dir_for_apps (str): 应用数据目录
        app_to_manage (str): 要管理的应用名称
        initial_files_source_root (str): 初始文件根目录
    
    Returns:
        Tuple[bool, str]: (验证是否通过, 错误信息)
    """
    if mode not in ["setup", "reset"]:
        return False, f"无效的模式: {mode}"
        
    if not all([base_dir_for_apps, app_to_manage, initial_files_source_root]):
        return False, "所有参数都不能为空"
        
    if not os.path.isabs(base_dir_for_apps):
        return False, f"base_dir_for_apps 必须是绝对路径: {base_dir_for_apps}"
        
    if not os.path.isabs(initial_files_source_root):
        return False, f"initial_files_source_root 必须是绝对路径: {initial_files_source_root}"
        
    # 验证目录权限
    try:
        if not os.path.exists(base_dir_for_apps):
            os.makedirs(base_dir_for_apps)
        test_file = os.path.join(base_dir_for_apps, ".test_write")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
    except (OSError, IOError) as e:
        return False, f"目录权限验证失败: {str(e)}"
        
    return True, ""

def manage_project_workflow(
    mode: str,
    base_dir_for_apps: str,
    app_to_manage: str,
    initial_files_source_root: str,
    progress_callback: Optional[Callable[[str, int], None]] = None
) -> bool:
    """
    管理项目环境的主要工作流程函数，支持 "setup" 和 "reset" 模式。

    Args:
        mode (str): 操作模式， "setup" 或 "reset"。
        base_dir_for_apps (str): 将在其中创建 [app_name]_dir 的基础目录。
        app_to_manage (str): 要管理的应用名称。
        initial_files_source_root (str): 初始文件所在的根目录。
        progress_callback (Optional[Callable[[str, int], None]]): 进度回调函数。

    Returns:
        bool: 表示操作是否整体成功。
    """
    total_steps = 3  # 总步骤数
    current_step = 0
    
    def update_progress(description: str):
        nonlocal current_step
        current_step += 1
        if progress_callback:
            progress_callback(description, int(current_step * 100 / total_steps))
        logger.info(f"{description} ({current_step}/{total_steps})")
    
    try:
        logger.info(f"开始执行工作流程: 模式 '{mode.upper()}' for app '{app_to_manage}'")
        
        # 步骤1: 验证配置
        update_progress("验证配置")
        valid, error_msg = validate_workflow_config(mode, base_dir_for_apps, app_to_manage, initial_files_source_root)
        if not valid:
            logger.error(f"配置验证失败: {error_msg}")
            return False
            
        # 步骤2: 创建目录结构
        update_progress("创建目录结构")
        file_dir = get_project_paths(base_dir_for_apps, app_to_manage)
        if not create_project_dir(file_dir):
            logger.error("创建目录结构失败")
            return False

        # 步骤3: 移动文件
        update_progress("移动文件")
        success = False
        if mode == "setup":
            success = move_original_data(initial_files_source_root, file_dir, app_to_manage)
        elif mode == "reset":
            success = move_original_data_back(file_dir, app_to_manage)

        # 步骤4: 处理原始数据
        update_progress("处理原始数据")
        raw_df = pd.read_csv(file_dir['UR'])
        processed_df = process_raw_data(raw_df)
        processed_df.to_csv(file_dir['UR'], index=False)
            
        if success:
            logger.info(f"工作流程 '{mode.upper()}' 执行成功")
        else:
            logger.error(f"工作流程 '{mode.upper()}' 执行失败")
        return success
        
    except Exception as e:
        logger.error(f"工作流执行过程中发生错误: {str(e)}")
        return False

def setup_project(mode: str = "setup") -> bool:
    """项目初始化设置"""
    try:
        # 1. 设置基础参数
        param_base_data_dir = os.path.join(PROJECT_ROOT, DATA_DIR_BASE_NAME)
        param_app_name = APP_NAME
        param_initial_files_root = PROJECT_ROOT
        
        # 2. 执行工作流
        workflow_success = manage_project_workflow(
            mode=mode,
            base_dir_for_apps=param_base_data_dir,
            app_to_manage=param_app_name,
            initial_files_source_root=param_initial_files_root
        )
        
        if not workflow_success:
            logger.error("工作流程执行失败")
            return False
            
        # 3. 根据模式输出相应信息
        if mode == "setup":
            logger.info("项目环境已准备就绪")
            logger.info(
                f"确保文件已被移入正确位置: {os.path.join(param_base_data_dir, f'{param_app_name}_dir', SDIR_00_RAW)}")
            
        elif mode == "reset":
            logger.info(f"文件已移回项目根目录: {PROJECT_ROOT}")
            
        return True

    except Exception as e:
        logger.error(f"项目设置过程出错: {str(e)}")
        return False

def run(mode: str):
    """
    运行项目设置或重置。

    Args:
        mode (str): 操作模式，可以是 "setup" 或 "reset"。
    """
    if mode not in ["setup", "reset"]:
        print(f"错误: 无效的模式 '{mode}'。必须是 'setup' 或 'reset'。")
        return

    success = setup_project(mode)
    if success:
        print(f"项目{mode}成功完成！")
    else:
        print(f"项目{mode}失败。请检查日志了解详细信息。")

if __name__ == "__main__":
    # 使用标准日志系统
    # logging.basicConfig(
    #     level=logging.INFO,
    #     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    # )
    
    # # 检查命令行参数
    # if len(sys.argv) != 2 or sys.argv[1] not in ["setup", "reset"]:
    #     print("用法: python parameters.py [setup|reset]")
    #     sys.exit(1)
        
    # run(sys.argv[1])
    run("setup")