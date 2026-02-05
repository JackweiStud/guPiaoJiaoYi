#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编码修复脚本 - 用于设置Python环境的编码
"""

import sys
import os
import locale

def fix_encoding():
    """修复Python环境的编码设置"""
    try:
        # 设置标准输出和标准错误的编码
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
        
        # 设置环境变量
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONLEGACYWINDOWSSTDIO'] = 'utf-8'
        
        # 尝试设置控制台编码
        try:
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
        except:
            pass
        
        # 设置默认编码
        if hasattr(sys, 'setdefaultencoding'):
            sys.setdefaultencoding('utf-8')
            
        print("编码设置完成:")
        print(f"  标准输出编码: {getattr(sys.stdout, 'encoding', 'unknown')}")
        print(f"  标准错误编码: {getattr(sys.stderr, 'encoding', 'unknown')}")
        print(f"  系统编码: {sys.getdefaultencoding()}")
        print(f"  区域设置: {locale.getpreferredencoding()}")
        
        return True
        
    except Exception as e:
        print(f"编码设置失败: {e}")
        return False

if __name__ == "__main__":
    fix_encoding() 