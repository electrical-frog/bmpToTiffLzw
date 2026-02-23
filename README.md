# bmpToTiffLzw

NAS 等に保存された **BMP（8bit 想定）** を、**画質を変えずに TIFF（LZW 圧縮 / 可逆）** へ一括変換するツールです。
**BMP は削除しません**（ユーザーが必要に応じて手動で削除してください）。

---

## 特徴

- **BMP → TIFF（LZW）** 一括変換（可逆圧縮・非破壊）
- **BMP はそのまま保持**（削除オプションなし）
- ディレクトリ配下を **再帰的に検索** して変換
- 起動時に **標準入力でフォルダパスを質問**。入力後は全自動
- 同名 TIFF が存在する場合は **スキップ**（`--overwrite` で上書き可）
- 変換中は **`.tmp` ファイルを経由してから rename**（中断時に壊れた TIFF を残さない）
- 1 ファイルが失敗しても **処理を継続** し、最後に **サマリ** を表示
- 変換エンジン: **ImageMagick**（優先）または **Pillow**（フォールバック）

---

## 動作環境

- Ubuntu（他の Linux でも動作すると思われます）
- Python 3.8 以上

---

## セットアップ

### ステップ 1: ImageMagick をインストールする（推奨）

```bash
sudo apt update
sudo apt install -y imagemagick
```

ImageMagick があれば Pillow は不要です。LZW が確実に効くうえ、処理も安定しています。

> **Pillow を使う場合（ImageMagick がない環境のフォールバック）**
>
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate
> pip install -r requirements.txt
> ```
>
> 両方入っている場合は **ImageMagick が優先** されます。

---

### ステップ 2: ImageMagick のリソース制限を緩和する（大きな画像を扱う場合は必須）

Ubuntu の ImageMagick はデフォルトのリソース制限がとても保守的です。
大きな BMP（目安: 1 ファイルあたり 20MB 超、または 7,000px 超）を変換しようとすると、
以下のようなエラーが出て変換に失敗します。

```
cache resources exhausted
width or height exceeds limit
```

`/etc/ImageMagick-6/policy.xml`（ImageMagick 7 の場合は `/etc/ImageMagick-7/policy.xml`）を
開いて、`<policymap>` 内のリソース設定を書き換えてください。

```bash
sudo nano /etc/ImageMagick-6/policy.xml
```

**変更前（Ubuntu デフォルト）:**

```xml
<policy domain="resource" name="memory" value="256MiB"/>
<policy domain="resource" name="map"    value="512MiB"/>
<policy domain="resource" name="width"  value="16KP"/>
<policy domain="resource" name="height" value="16KP"/>
<policy domain="resource" name="area"   value="128MP"/>
<policy domain="resource" name="disk"   value="1GiB"/>
```

**変更後:**

```xml
<policy domain="resource" name="memory" value="2GiB"/>
<policy domain="resource" name="map"    value="4GiB"/>
<policy domain="resource" name="width"  value="65KP"/>
<policy domain="resource" name="height" value="65KP"/>
<policy domain="resource" name="area"   value="1GP"/>
<policy domain="resource" name="disk"   value="8GiB"/>
```

各設定値の意味:

| 設定 | 変更前 | 変更後 | 意味 |
|---|---|---|---|
| `memory` | 256MiB | 2GiB | RAM 上のピクセルキャッシュ上限 |
| `map` | 512MiB | 4GiB | メモリマップ上限 |
| `width` | 16KP（16,000px） | 65KP（65,000px） | 画像の幅の上限 |
| `height` | 16KP（16,000px） | 65KP（65,000px） | 画像の高さの上限 |
| `area` | 128MP（1.28億px） | 1GP（10億px） | 一度に扱えるピクセル数の上限 |
| `disk` | 1GiB | 8GiB | RAM が足りない場合のディスクキャッシュ上限 |

> **`disk` の値について**
> ディスクキャッシュは作業ディスクの空き容量の範囲で使われます。
> 実際に 8GiB が消費されるわけではなく、上限として指定するものです。
> ローカル SSD など十分な空き容量があることを確認してから設定してください。

---

## 使い方

### 基本実行

```bash
python3 convertBmpToTiff.py
```

起動すると変換エンジンを表示した後、フォルダパスを質問します。

```
変換エンジン: ImageMagick (convert)
変換対象のフォルダパスを入力してください: /mnt/nas/filmScans
```

パスを入力すると、以降は全自動で変換します。

### 実行例（出力イメージ）

```
変換エンジン: ImageMagick (convert)
変換対象のフォルダパスを入力してください: /home/user/photos

/home/user/photos をスキャン中...
5 件の BMP ファイルを検出しました。

[1/5] OK       /home/user/photos/scan001.bmp
           → /home/user/photos/scan001.tif
[2/5] OK       /home/user/photos/scan002.bmp
           → /home/user/photos/scan002.tif
[3/5] skip     /home/user/photos/scan003.bmp
[4/5] FAILED   /home/user/photos/scan004.bmp
           reason: ...エラー詳細...
[5/5] OK       /home/user/photos/scan005.bmp
           → /home/user/photos/scan005.tif

────────────────────────────────────────────────────────────
処理結果サマリ
────────────────────────────────────────────────────────────
  変換成功   : 3
  スキップ   : 1
  失敗       : 1

失敗したファイル:
  /home/user/photos/scan004.bmp
    ...エラー詳細...
────────────────────────────────────────────────────────────
```

失敗があっても処理は最後まで継続します。再実行すると成功済みのファイルはスキップされるので、
失敗分だけを自動的にリトライできます。

---

## CLI オプション一覧

| オプション | デフォルト | 説明 |
|---|---|---|
| *(なし)* | — | 標準入力でフォルダを質問して全自動変換 |
| `--no-recursive` | オフ | サブディレクトリを再帰処理しない |
| `--overwrite` | オフ | 既存の TIFF を上書きする |
| `--dryRun` | オフ | 変換せずに処理内容だけ表示する |
| `--jobs N` | `2` | 並列変換数（NAS 環境では `1` を推奨） |
| `--ext tif\|tiff` | `tif` | 出力ファイルの拡張子 |
| `--dst DIR` | *(入力と同じ)* | 出力先ディレクトリ（構造を維持して配置） |

### オプション使用例

```bash
# 変換内容を事前確認（ファイルは書かない）
python3 convertBmpToTiff.py --dryRun

# 既存 TIFF を上書きして再変換
python3 convertBmpToTiff.py --overwrite

# 拡張子を .tiff にする
python3 convertBmpToTiff.py --ext tiff

# 出力先を別ディレクトリに（ディレクトリ構造を維持）
python3 convertBmpToTiff.py --dst /mnt/nas/tiffs

# NAS 上のファイルを直接変換する場合（並列数を 1 に下げて安全に）
python3 convertBmpToTiff.py --jobs 1

# サブディレクトリを処理しない
python3 convertBmpToTiff.py --no-recursive
```

---

## 出力ファイルについて

入力と同じディレクトリ（デフォルト）に、元ファイル名の拡張子だけ変えた TIFF が作成されます。

```
/photos/
  scan001.bmp   ← そのまま残る
  scan001.tif   ← 新規作成（LZW 圧縮）
  scan002.bmp   ← そのまま残る
  scan002.tif   ← 新規作成（LZW 圧縮）
```

`--dst` を指定した場合は、元のディレクトリ構造を維持したまま出力先に配置します。

```
入力: /bmp/2024/scan001.bmp  + --dst /tiff
出力: /tiff/2024/scan001.tif
```

---

## NAS 上で実行する場合の注意

BMP が巨大かつ枚数が多い場合、NAS 上で直接変換すると以下がボトルネックになりがちです。

- NAS の HDD I/O（スピンアップ待ち・ランダムアクセスが遅い）
- SMB 経由の書き込み遅延
- 並列変換による I/O 競合

**推奨手順:**

1. ローカル SSD に BMP フォルダをコピー
2. ローカルで変換（`python3 convertBmpToTiff.py`）
3. 生成した TIFF だけ NAS へ戻す

直接 NAS で変換する場合は `--jobs 1` を指定してください。

---

## LZW 圧縮の確認方法

変換後のファイルが正しく LZW 圧縮されているか確認できます。

### ImageMagick で確認

```bash
identify -verbose example.tif | grep -i compression
```

出力例:

```
Compression: LZW
```

### tiffinfo で確認（libtiff-tools が必要）

```bash
sudo apt install -y libtiff-tools
tiffinfo example.tif
```

出力中に `Compression Scheme: LZW` と表示されれば OK です。

---

## 動作確認手順

はじめてセットアップしたあと、以下の手順で正しく動いているか確認できます。

```bash
# 1. テスト用の小さな BMP を作成する
#    （ImageMagick 7 なら magick、6 なら convert を使う）
mkdir -p /tmp/bmptest/sub
convert -size 10x10 xc:red  /tmp/bmptest/a.bmp
convert -size 10x10 xc:blue /tmp/bmptest/sub/b.bmp

# 2. 変換実行（BMP が残ることを確認）
python3 convertBmpToTiff.py
# → プロンプトに /tmp/bmptest と入力

ls /tmp/bmptest/
# a.bmp と a.tif が両方あること

# 3. 再実行でスキップされることを確認
python3 convertBmpToTiff.py
# → "skip" が表示されること

# 4. --overwrite で上書きされることを確認
python3 convertBmpToTiff.py --overwrite
# → "OK" が表示されること

# 5. LZW 圧縮を確認
identify -verbose /tmp/bmptest/a.tif | grep -i compression
# → Compression: LZW

# 6. dryRun でファイルが増えないことを確認
rm /tmp/bmptest/a.tif /tmp/bmptest/sub/b.tif
python3 convertBmpToTiff.py --dryRun
ls /tmp/bmptest/*.tif 2>/dev/null || echo "TIF なし（期待通り）"

# 7. 後片付け
rm -rf /tmp/bmptest
```

---

## トラブルシュート

### `cache resources exhausted` または `width or height exceeds limit`

ImageMagick のリソース制限に引っかかっています。
上記「[ステップ 2: ImageMagick のリソース制限を緩和する](#ステップ-2-imagemagick-のリソース制限を緩和する大きな画像を扱う場合は必須)」の手順で `policy.xml` を修正してください。

修正後は失敗したファイルのみを再変換できます（成功済みはスキップされます）。

```bash
python3 convertBmpToTiff.py --jobs 1
```

### `Error: neither ImageMagick nor Pillow is available.`

変換エンジンが見つかりません。どちらかをインストールしてください。

```bash
sudo apt install imagemagick
# または
pip install pillow
```

### `identify: not authorized` または `convert: not authorized`

ImageMagick のコーダーポリシーで BMP や TIFF が制限されています。
`policy.xml` で該当フォーマットの権限を確認してください。

```bash
grep -i 'BMP\|TIFF' /etc/ImageMagick-6/policy.xml
```

`rights="none"` になっていれば `rights="read|write"` に変更します。

### パスにスペースや日本語が含まれる

サブプロセス呼び出しはリスト形式で引数を渡しているため、スペース・日本語を含むパスでも正しく動作します。

### 変換途中に中断された（`.tmp` ファイルが残った）

`.tmp` ファイルは書き込み途中の状態です。削除してから再実行してください。

```bash
find /path/to/photos -name '*.tmp' -delete
python3 convertBmpToTiff.py
```

---

## ライセンス

MIT
