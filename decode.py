#!/usr/bin/env python3
"""
Base64编码 -> 二进制 -> ZSTD解压 -> MessagePack -> JSON

用法:
    python decode_to_json.py <编码字符串或文件> [输出JSON文件]

示例:
    # 直接输入编码
    python decode_to_json.py "KLUv_WCo..." output.json

    # 从文件读取编码
    python decode_to_json.py encoding.txt result.json

    # 不指定输出文件名（自动生成）
    python decode_to_json.py "KLUv_WCo..."
"""

import base64
import zlib
import zstandard as zstd
import msgpack
import json
import sys
import os


def decode_to_binary(base64_str):
    """
    解码Base64编码，返回二进制数据

    Args:
        base64_str: Base64编码字符串

    Returns:
        解码后的二进制数据，失败返回 None
    """
    base64_str = base64_str.strip()

    if not base64_str:
        print("错误: 输入为空!")
        return None

    # URL安全Base64转换为标准Base64
    standard_base64 = base64_str.replace('-', '+').replace('_', '/')
    padding_needed = 4 - (len(standard_base64) % 4)
    if padding_needed != 4:
        standard_base64 += '=' * padding_needed

    # Base64解码
    try:
        decoded_data = base64.b64decode(standard_base64)
    except Exception as e:
        print(f"Base64解码失败: {e}")
        return None

    # 尝试zlib解压
    decompressed_data = None
    try:
        decompressed_data = zlib.decompress(decoded_data)
    except zlib.error:
        try:
            decompressed_data = zlib.decompress(decoded_data, 16 + zlib.MAX_WBITS)
        except zlib.error:
            try:
                decompressed_data = zlib.decompress(decoded_data, -15)
            except zlib.error:
                decompressed_data = decoded_data

    return decompressed_data


def decompress_zstd(binary_data):
    """
    使用ZSTD解压数据

    Args:
        binary_data: 二进制数据

    Returns:
        解压后的数据，失败返回 None
    """
    try:
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(binary_data)
    except Exception as e:
        print(f"ZSTD解压失败: {e}")
        return None


def bytes_to_str(obj):
    """递归将bytes对象转换为utf-8字符串"""
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            return obj
    elif isinstance(obj, dict):
        return {bytes_to_str(k): bytes_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [bytes_to_str(item) for item in obj]
    return obj


def msgpack_to_json(binary_data):
    """
    将MessagePack数据转换为JSON

    Args:
        binary_data: MessagePack二进制数据

    Returns:
        Python对象（可序列化为JSON），失败返回 None
    """
    try:
        data = msgpack.unpackb(binary_data, raw=True, strict_map_key=False)
        data = bytes_to_str(data)

        # 尝试解析嵌套的JSON字符串
        if 'content' in data and isinstance(data['content'], str):
            try:
                data['content'] = json.loads(data['content'])
            except json.JSONDecodeError:
                pass  # 如果不是有效JSON，保持原样

        return data
    except Exception as e:
        print(f"MessagePack解析失败: {e}")
        return None


def process_to_json(input_arg, output_file=None):
    """
    完整处理流程: Base64 -> 二进制 -> ZSTD -> MessagePack -> JSON

    Args:
        input_arg: Base64编码字符串或文件路径
        output_file: 输出JSON文件路径，默认自动生成
    """
    # 1. 获取输入
    if os.path.exists(input_arg):
        with open(input_arg, 'r', encoding='utf-8') as f:
            base64_str = f.read().strip()
        print(f"从文件读取: {input_arg}")
    else:
        base64_str = input_arg

    # 2. Base64解码
    print(f"步骤1: Base64解码 (输入长度: {len(base64_str)} 字符)")
    binary_data = decode_to_binary(base64_str)
    if binary_data is None:
        return False
    print(f"  → 解码成功: {len(binary_data)} 字节")

    # 3. ZSTD解压
    print("步骤2: ZSTD解压")
    zstd_data = decompress_zstd(binary_data)
    if zstd_data is None:
        return False
    print(f"  → 解压成功: {len(zstd_data)} 字节")

    # 4. MessagePack转JSON
    print("步骤3: MessagePack解析")
    json_data = msgpack_to_json(zstd_data)
    if json_data is None:
        return False
    print(f"  → 解析成功")

    # 5. 保存JSON
    if output_file is None:
        output_file = "decoded_output.json"
        print(f"输出文件未指定，使用默认: {output_file}")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    print(f"\n成功! 已保存到: {output_file}")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_arg = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not process_to_json(input_arg, output_file):
        sys.exit(1)


if __name__ == "__main__":
    main()
