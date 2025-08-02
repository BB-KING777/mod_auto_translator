import os
import zipfile
import json
import time
from pathlib import Path
import re
from typing import Dict, List, Optional
from google import genai

class ModTranslator:
    def __init__(self, gemini_api_key: str):
        self.api_key = gemini_api_key
        # 新しいGemini SDKクライアントを初期化
        self.client = genai.Client(api_key=gemini_api_key)
        self.translation_delay = 1  # API呼び出し間の遅延（秒）
    
    def find_language_files_in_jar(self, jar_path: str) -> List[Dict]:
        """JARファイル内のen_us言語ファイルのみを検索する"""
        language_files = []
        
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                for file_info in jar.filelist:
                    file_path = file_info.filename
                    
                    # en_us.jsonファイルのみを対象とする
                    lang_pattern = re.compile(r'(assets|data)/[^/]+/lang/en_us\.json$', re.IGNORECASE)
                    
                    if lang_pattern.match(file_path):
                        try:
                            content = jar.read(file_info).decode('utf-8')
                            json_data = json.loads(content)
                            
                            language_files.append({
                                'path': file_path,
                                'content': json_data,
                                'mod_id': self.extract_mod_id(file_path),
                                'lang_code': self.extract_lang_code(file_path)
                            })
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            continue
                            
        except zipfile.BadZipFile:
            print(f"警告: {jar_path} は有効なJARファイルではありません")
        except Exception as e:
            print(f"エラー: {jar_path} の処理中にエラーが発生しました: {e}")
        
        return language_files
    
    def extract_mod_id(self, file_path: str) -> str:
        """ファイルパスからMOD IDを抽出"""
        parts = file_path.split('/')
        if len(parts) >= 3 and parts[1]:
            return parts[1]
        return "unknown"
    
    def extract_lang_code(self, file_path: str) -> str:
        """ファイルパスから言語コードを抽出"""
        filename = os.path.basename(file_path)
        return os.path.splitext(filename)[0]
    
    def translate_json_with_gemini(self, json_data: Dict, source_lang: str = "English") -> Optional[Dict]:
        """Gemini APIを使ってJSONデータを翻訳"""
        try:
            # JSONを文字列として整形
            json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
            
            # DarkRPG専用プロンプトを作成
            prompt = f"""以下はMinecraftのDarkRPGモッドパックの言語ファイル（JSON形式）です。
このJSONの値部分のみを英語から日本語に翻訳してください。
キー部分は変更しないでください。
翻訳後のJSONのみを返してください。説明文は不要です。

DarkRPG翻訳ルール:
- 世界観：ダークファンタジー、吸血鬼、ドラゴン、魔法、ダークソウル風の重厚な雰囲気
- アイテム/装備：呪われた、血の、闇の、古代の、禁断の、などダークな表現を使用
- 魔法関連：「魔術」「呪文」「儀式」「血の魔法」など重厚な用語
- 生物/敵：「魔物」「不死者」「古き者」などファンタジー色の強い名称
- UI要素：冒険者、探索者などRPG的表現を使用
- 吸血鬼要素：「血族」「夜の子」「血の渇き」など独特の表現
- 口調：格調高く、やや古風で重厚感のある日本語
- 固有名詞：英語のままでも可、ただし雰囲気に合わせてカタカナ化も検討
- JSONの構造とキーは絶対に変更しない

翻訳例：
"Cursed Blade" → "呪われし刃"
"Blood Magic" → "血の魔術"
"Ancient Tome" → "古代の魔導書"
"Vampire Lord" → "血族の王"
"Quest Giver" → "依頼人"

{json_str}"""

            # 新しいSDKを使用してAPI呼び出し
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt,
                config={
                    "temperature": 0.3,
                    "top_k": 40,
                    "top_p": 0.95,
                    "max_output_tokens": 8192,
                    "response_modalities": ["TEXT"],
                    "thinking_config": {"thinking_budget": 0}  # thinking機能を無効化
                }
            )
            
            if response.text:
                translated_text = response.text
                
                # 翻訳結果からJSONを抽出
                try:
                    # コードブロックがある場合は除去
                    if '```json' in translated_text:
                        start = translated_text.find('```json') + 7
                        end = translated_text.find('```', start)
                        if end != -1:
                            translated_text = translated_text[start:end].strip()
                    elif '```' in translated_text:
                        start = translated_text.find('```') + 3
                        end = translated_text.find('```', start)
                        if end != -1:
                            translated_text = translated_text[start:end].strip()
                    
                    # JSONとして解析
                    translated_json = json.loads(translated_text)
                    return translated_json
                except json.JSONDecodeError as e:
                    print(f"翻訳結果のJSON解析エラー: {e}")
                    print(f"応答内容: {translated_text[:500]}...")
                    return None
            else:
                print("APIからの応答が空です")
                return None
                
        except Exception as e:
            print(f"翻訳中にエラーが発生しました: {e}")
            return None
    
    def save_translated_json_to_jar(self, jar_path: str, original_lang_file: Dict, translated_content: Dict):
        """翻訳されたJSONをJARファイル内の元の場所に追加"""
        import tempfile
        import shutil
        
        # 元のパスからja_jp.jsonのパスを生成
        original_path = original_lang_file['path']
        ja_jp_path = original_path.replace('en_us.json', 'ja_jp.json')
        
        try:
            # 一時ディレクトリを作成
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_jar_path = os.path.join(temp_dir, 'temp.jar')
                
                # 元のJARファイルを一時ファイルにコピー
                shutil.copy2(jar_path, temp_jar_path)
                
                # JARファイルを読み書きモードで開く
                with zipfile.ZipFile(temp_jar_path, 'a') as jar:
                    # 翻訳されたJSONを文字列として準備
                    translated_json_str = json.dumps(translated_content, ensure_ascii=False, indent=2)
                    
                    # JARファイルに新しいファイルを追加
                    jar.writestr(ja_jp_path, translated_json_str.encode('utf-8'))
                
                # バックアップを作成
                backup_path = jar_path + '.backup'
                if not os.path.exists(backup_path):
                    shutil.copy2(jar_path, backup_path)
                    print(f"    バックアップを作成: {backup_path}")
                
                # 更新されたJARファイルを元の場所に移動
                shutil.move(temp_jar_path, jar_path)
                
            print(f"    翻訳済みファイルをJAR内に追加: {ja_jp_path}")
            return True
            
        except Exception as e:
            print(f"    JARファイル更新エラー: {e}")
            return False
    
    def translate_mod_files(self, directory_path: str):
        """指定ディレクトリ内のMODファイルを翻訳"""
        directory = Path(directory_path)
        
        if not directory.exists():
            print(f"エラー: ディレクトリ {directory_path} が存在しません")
            return
        
        jar_files = list(directory.glob("*.jar"))
        
        if not jar_files:
            print(f"警告: {directory_path} にJARファイルが見つかりません")
            return
        
        print(f"{len(jar_files)}個のJARファイルからen_us.jsonを処理します")
        print("="*60)
        
        total_files = 0
        successful_translations = 0
        
        for jar_file in jar_files:
            print(f"\n処理中: {jar_file.name}")
            language_files = self.find_language_files_in_jar(str(jar_file))
            
            if not language_files:
                print("  en_us.jsonファイルが見つかりません - スキップ")
                continue
            
            print(f"  {len(language_files)}個のen_us.jsonファイルを発見")
            
            for lang_file in language_files:
                total_files += 1
                print(f"  翻訳中: {lang_file['path']} (en_us → ja_jp)")
                
                # 翻訳実行（英語から日本語）
                translated_content = self.translate_json_with_gemini(
                    lang_file['content'], 
                    "English"
                )
                
                if translated_content:
                    # 翻訳済みファイルをJARファイル内に保存
                    if self.save_translated_json_to_jar(str(jar_file), lang_file, translated_content):
                        successful_translations += 1
                        print(f"    ✓ 翻訳完了")
                    else:
                        print(f"    ✗ 保存失敗")
                else:
                    print(f"    ✗ 翻訳失敗")
                
                # API制限を避けるための遅延
                if total_files < sum(len(self.find_language_files_in_jar(str(jf))) for jf in jar_files):
                    print(f"    {self.translation_delay}秒待機中...")
                    time.sleep(self.translation_delay)
        
        print("\n" + "="*60)
        print("翻訳完了!")
        print(f"処理したファイル数: {total_files}")
        print(f"成功した翻訳数: {successful_translations}")
        print(f"失敗した翻訳数: {total_files - successful_translations}")
        print(f"翻訳済みファイルは各JARファイル内に ja_jp.json として追加されました")
        print(f"元のJARファイルは .backup として保存されています")

def main():
    print("MOD翻訳ツール（Gemini API版）")
    print("="*60)
    
    # APIキー入力
    api_key = input("Gemini APIキーを入力してください: ").strip()
    if not api_key:
        print("APIキーが必要です")
        return
    
    # ディレクトリ入力
    directory = input("JARファイルがあるディレクトリパスを入力してください（空白で現在のディレクトリ）: ").strip()
    if not directory:
        directory = "."
    
    print(f"\nディレクトリ: {os.path.abspath(directory)}")
    
    # 翻訳実行確認
    confirm = input("翻訳を開始しますか？ (y/n): ").strip().lower()
    if confirm != 'y':
        print("キャンセルしました")
        return
    
    # 翻訳実行
    translator = ModTranslator(api_key)
    translator.translate_mod_files(directory)

if __name__ == "__main__":
    main()