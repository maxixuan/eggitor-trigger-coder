#!/usr/bin/env python3
"""
JSON -> msgpack -> zstd压缩 -> URL安全Base64编码 -> 纯文本文件

用法:
    python encode_json.py <输入JSON文件> [输出文本文件]

示例:
    python encode_json.py bbb1.json output.txt
    python encode_json.py bbb1.json  # 自动生成输出文件名
"""

import base64
import msgpack
import json
import sys
import os
import zstandard as zstd


def json_to_msgpack_data(json_file):
    """
    将JSON文件转换为MessagePack二进制数据

    与 json_to_msgpack.py 逻辑一致，确保生成与原始相同的 msgpack

    Args:
        json_file: 输入的JSON文件路径

    Returns:
        MessagePack二进制数据
    """
    # 读取JSON文件
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 构建保持原始顺序的数据，使用 bytes 键
    # 顶层键顺序: content, content_type, custom_info
    msgpack_data = {}

    # 处理 content 字段（需要转回 JSON 字符串）
    if 'content' in data:
        content_value = data['content']
        if isinstance(content_value, dict):
            # 使用默认格式（带空格），与原始保持一致
            content_value = json.dumps(content_value, ensure_ascii=True, sort_keys=False)
        # 转为 bytes 以匹配原始的 bin 格式编码
        if isinstance(content_value, str):
            content_value = content_value.encode('utf-8')
        msgpack_data[b'content'] = content_value

    # 处理 content_type 字段
    if 'content_type' in data:
        msgpack_data[b'content_type'] = data['content_type']

    # 处理 custom_info 字段（需要处理整数键和 bytes 子键）
    if 'custom_info' in data:
        custom_info = {}
        for key, value in data['custom_info'].items():
            # 尝试将字符串键转为整数
            try:
                int_key = int(key)
            except ValueError:
                int_key = key

            # 处理子结构中的 bytes 键和值
            new_value = {}
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    # 顶层 custom_info 的子键和字符串值都使用 bytes
                    bytes_key = sub_key.encode('utf-8')
                    if isinstance(sub_value, str):
                        # 某些字符串值需要转为 bytes（如 trigger_group_id）
                        if sub_key in ('trigger_group_id',):
                            new_value[bytes_key] = sub_value.encode('utf-8')
                        else:
                            new_value[bytes_key] = sub_value
                    elif isinstance(sub_value, dict):
                        # 处理嵌套 dict 的键
                        nested = {}
                        for nk, nv in sub_value.items():
                            nested[nk.encode('utf-8')] = nv
                        new_value[bytes_key] = nested
                    else:
                        new_value[bytes_key] = sub_value

                # 处理 local_used_var - 保持 bytes 键
                if b'local_used_var' in new_value:
                    local_used_var = {}
                    for lk, lv in new_value[b'local_used_var'].items():
                        # local_used_var 的键使用 bytes
                        if isinstance(lk, str):
                            lk = lk.encode('utf-8')
                        local_used_var[lk] = lv
                    new_value[b'local_used_var'] = local_used_var
            else:
                new_value = value

            custom_info[int_key] = new_value
        msgpack_data[b'custom_info'] = custom_info

    # 打包为MessagePack
    return msgpack.packb(msgpack_data)


def compress_zstd(binary_data, level=10):
    """
    使用ZSTD压缩数据

    Args:
        binary_data: 二进制数据
        level: 压缩级别 (默认10)

    Returns:
        压缩后的二进制数据
    """
    cctx = zstd.ZstdCompressor(level=level)
    return cctx.compress(binary_data)


def encode_to_urlsafe_base64(binary_data):
    """
    将二进制数据编码为URL安全Base64字符串

    Args:
        binary_data: 二进制数据

    Returns:
        URL安全Base64编码字符串（保留填充字符）
    """
    base64_str = base64.b64encode(binary_data).decode('utf-8')
    # URL安全处理：+ -> -, / -> _，保留尾部的 = 填充
    return base64_str.replace('+', '-').replace('/', '_')


def process_json_to_encoding(input_json_file, output_text_file=None):
    """
    完整处理流程: JSON -> msgpack -> zstd压缩 -> URL安全Base64 -> 纯文本

    Args:
        input_json_file: 输入的JSON文件路径
        output_text_file: 输出的纯文本文件路径，默认自动生成

    Returns:
        成功返回True，失败返回False
    """
    # 检查输入文件
    if not os.path.exists(input_json_file):
        print(f"错误: 文件不存在 - {input_json_file}")
        return False

    print(f"输入文件: {input_json_file}")
    print(f"文件大小: {os.path.getsize(input_json_file)} 字节")
    print()

    # 步骤1: JSON -> msgpack
    print("步骤1: JSON -> msgpack")
    msgpack_data = json_to_msgpack_data(input_json_file)
    if msgpack_data is None:
        return False
    print(f"  -> msgpack 数据: {len(msgpack_data)} 字节")
    print(f"  -> 文件头: {msgpack_data[:4].hex().upper()}")
    print()

    # 步骤2: zstd 压缩
    print("步骤2: zstd 压缩 (level=10, --no-check)")
    compressed_data = compress_zstd(msgpack_data, level=10)
    if compressed_data is None:
        return False
    print(f"  -> 压缩后: {len(compressed_data)} 字节")
    print(f"  -> 压缩率: {len(compressed_data) / len(msgpack_data) * 100:.1f}%")
    print()

    # 步骤3: URL安全Base64编码
    print("步骤3: URL安全Base64编码")
    encoded_str = encode_to_urlsafe_base64(compressed_data)
    print(f"  -> 编码长度: {len(encoded_str)} 字符")
    print()

    # 步骤4: 保存到文本文件
    if output_text_file is None:
        base_name = os.path.splitext(os.path.basename(input_json_file))[0]
        output_text_file = f"{base_name}_encoding.txt"
        print(f"输出文件未指定，使用默认: {output_text_file}")

    with open(output_text_file, 'w', encoding='utf-8') as f:
        f.write(encoded_str)

    print(f"\n成功! 编码已保存到: {output_text_file}")
    print(f"编码长度: {len(encoded_str)} 字符")
    print(f"\n编码预览 (前100字符):")
    print(encoded_str[:100] + "..." if len(encoded_str) > 100 else encoded_str)

    return True


def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_json_file = sys.argv[1]
    output_text_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not process_json_to_encoding(input_json_file, output_text_file):
        sys.exit(1)


if __name__ == '__main__':
    main()
