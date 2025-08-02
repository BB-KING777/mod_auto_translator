# -*- coding: utf-8 -*-
"""
Created on Sun Aug  3 02:36:40 2025

@author: Shuta Wakamiya
"""

import os
import zipfile
import json
from pathlib import Path
import re

def find_language_files_in_jar(jar_path):
    """
    JARファイル内の言語ファイルを検索する
    """
    language_files = []
    
    try:
        with zipfile.ZipFile(jar_path, 'r') as jar:
            # JARファイル内の全ファイルをチェック
            for file_info in jar.filelist:
                file_path = file_info.filename
                
                # 言語ファイルのパターンをチェック
                # 一般的なパターン: assets/*/lang/*.json
                # MODによっては data/*/lang/*.json の場合もある
                lang_pattern = re.compile(r'(assets|data)/[^/]+/lang/[^/]+\.json$', re.IGNORECASE)
                
                if lang_pattern.match(file_path):
                    # ファイルの内容を確認（JSONかどうか）
                    try:
                        content = jar.read(file_info).decode('utf-8')
                        # JSONとして解析可能かチェック
                        json.loads(content)
                        
                        language_files.append({
                            'path': file_path,
                            'size': file_info.file_size,
                            'mod_id': extract_mod_id(file_path),
                            'lang_code': extract_lang_code(file_path)
                        })
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        # JSONでない場合はスキップ
                        continue
                        
    except zipfile.BadZipFile:
        print(f"警告: {jar_path} は有効なJARファイルではありません")
    except Exception as e:
        print(f"エラー: {jar_path} の処理中にエラーが発生しました: {e}")
    
    return language_files

def extract_mod_id(file_path):
    """
    ファイルパスからMOD IDを抽出
    """
    # assets/modid/lang/... または data/modid/lang/... からmodidを抽出
    parts = file_path.split('/')
    if len(parts) >= 3 and parts[1]:
        return parts[1]
    return "unknown"

def extract_lang_code(file_path):
    """
    ファイルパスから言語コードを抽出
    """
    filename = os.path.basename(file_path)
    # .jsonを除去して言語コードを取得
    return os.path.splitext(filename)[0]

def scan_directory_for_mods(directory_path):
    """
    指定されたディレクトリ内のすべてのJARファイルをスキャン
    """
    directory = Path(directory_path)
    
    if not directory.exists():
        print(f"エラー: ディレクトリ {directory_path} が存在しません")
        return {}
    
    jar_files = list(directory.glob("*.jar"))
    
    if not jar_files:
        print(f"警告: {directory_path} にJARファイルが見つかりません")
        return {}
    
    print(f"{len(jar_files)}個のJARファイルを発見しました")
    
    all_results = {}
    
    for jar_file in jar_files:
        print(f"\n処理中: {jar_file.name}")
        language_files = find_language_files_in_jar(jar_file)
        
        if language_files:
            all_results[str(jar_file)] = language_files
            print(f"  {len(language_files)}個の言語ファイルを発見")
            
            # 詳細情報を表示
            for lang_file in language_files:
                print(f"    MOD ID: {lang_file['mod_id']}")
                print(f"    言語: {lang_file['lang_code']}")
                print(f"    パス: {lang_file['path']}")
                print(f"    サイズ: {lang_file['size']} bytes")
                print()
        else:
            print("  言語ファイルが見つかりませんでした")
    
    return all_results

def generate_report(results):
    """
    スキャン結果のレポートを生成
    """
    if not results:
        print("言語ファイルが見つかりませんでした。")
        return
    
    print("\n" + "="*60)
    print("スキャン結果サマリー")
    print("="*60)
    
    total_mods = len(results)
    total_lang_files = sum(len(files) for files in results.values())
    
    print(f"スキャンしたMOD数: {total_mods}")
    print(f"発見した言語ファイル数: {total_lang_files}")
    
    # MOD別の統計
    print("\nMOD別言語ファイル数:")
    for jar_path, lang_files in results.items():
        jar_name = os.path.basename(jar_path)
        mod_ids = set(f['mod_id'] for f in lang_files)
        lang_codes = set(f['lang_code'] for f in lang_files)
        
        print(f"  {jar_name}:")
        print(f"    MOD ID: {', '.join(mod_ids)}")
        print(f"    言語: {', '.join(sorted(lang_codes))}")
        print(f"    ファイル数: {len(lang_files)}")

def main():
    """
    メイン実行関数
    """
    # 現在のディレクトリをデフォルトとする
    directory = input("JARファイルがあるディレクトリパスを入力してください（空白で現在のディレクトリ）: ").strip()
    
    if not directory:
        directory = "."
    
    print(f"\nディレクトリをスキャン中: {os.path.abspath(directory)}")
    print("-" * 60)
    
    results = scan_directory_for_mods(directory)
    generate_report(results)
    
    # 結果をJSONファイルに保存するかどうか
    if results:
        save_json = input("\n結果をJSONファイルに保存しますか？ (y/n): ").strip().lower()
        if save_json == 'y':
            output_file = "mod_language_scan_result.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"結果を {output_file} に保存しました")

if __name__ == "__main__":
    main()