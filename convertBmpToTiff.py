#!/usr/bin/env python3
"""
convertBmpToTiff.py  —  BMP → TIFF (LZW) 一括変換ツール

使い方:
    python3 convertBmpToTiff.py [オプション]

起動後、変換対象のフォルダパスを標準入力で尋ねます。
入力後は全自動で変換を実行します。BMP ファイルは削除しません。
"""

import argparse
import pathlib
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# 変換エンジン検出
# ─────────────────────────────────────────────────────────────────────────────

def _detect_imagemagick() -> Optional[str]:
    """'magick' または 'convert' (ImageMagick) が使えれば返す。なければ None。"""
    for cmd in ('magick', 'convert'):
        if not shutil.which(cmd):
            continue
        try:
            r = subprocess.run(
                [cmd, '--version'],
                capture_output=True, text=True, timeout=5,
            )
            if 'ImageMagick' in (r.stdout + r.stderr):
                return cmd
        except Exception:
            pass
    return None


def _detect_pillow() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 変換処理
# ─────────────────────────────────────────────────────────────────────────────

def _convert_imagemagick(cmd: str, src: pathlib.Path, dst: pathlib.Path) -> None:
    """ImageMagick で BMP → TIFF(LZW) 変換。失敗時は .tmp を削除して例外を送出。"""
    tmp = dst.with_suffix('.tmp')
    try:
        r = subprocess.run(
            [cmd, str(src), '-compress', 'LZW', f'tiff:{tmp}'],
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip() or f'{cmd} が終了コード {r.returncode} で失敗')
        tmp.rename(dst)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _convert_pillow(src: pathlib.Path, dst: pathlib.Path) -> None:
    """Pillow で BMP → TIFF(LZW) 変換。失敗時は .tmp を削除して例外を送出。"""
    from PIL import Image
    tmp = dst.with_suffix('.tmp')
    try:
        with Image.open(src) as img:
            # 'tiff_lzw' が Pillow の LZW TIFF 識別子
            img.save(str(tmp), format='TIFF', compression='tiff_lzw')
        tmp.rename(dst)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


# ─────────────────────────────────────────────────────────────────────────────
# ファイル収集・パス解決
# ─────────────────────────────────────────────────────────────────────────────

def _collect_bmp(root: pathlib.Path, recursive: bool) -> List[pathlib.Path]:
    """root 配下の .bmp ファイルを大文字小文字問わず収集してソートして返す。"""
    iterator = root.rglob('*') if recursive else root.glob('*')
    return sorted(
        p for p in iterator
        if p.is_file() and p.suffix.lower() == '.bmp'
    )


def _output_path(
    src: pathlib.Path,
    src_root: pathlib.Path,
    dst_root: Optional[pathlib.Path],
    ext: str,
) -> pathlib.Path:
    """
    出力 TIFF パスを決定する。
    - dst_root=None → src と同じディレクトリ
    - dst_root 指定 → src_root からの相対パスを dst_root 配下に再現
    """
    out_name = src.stem + '.' + ext
    if dst_root is None:
        return src.parent / out_name
    rel = src.parent.relative_to(src_root)
    out_dir = dst_root / rel
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / out_name


# ─────────────────────────────────────────────────────────────────────────────
# 1ファイル処理（スレッドで呼び出し）
# ─────────────────────────────────────────────────────────────────────────────

def _process_file(
    src: pathlib.Path,
    dst: pathlib.Path,
    *,
    overwrite: bool,
    dry_run: bool,
    im_cmd: Optional[str],
) -> Tuple[str, Optional[str]]:
    """
    1ファイルを変換する。
    戻り値: (status, error_message_or_None)
      status: 'converted' | 'skipped' | 'would_convert' | 'would_skip' | 'failed'
    """
    exists = dst.exists()

    if dry_run:
        if exists and not overwrite:
            return ('would_skip', None)
        action = 'overwrite' if exists else 'convert'
        return ('would_convert', action)

    if exists and not overwrite:
        return ('skipped', None)

    try:
        if im_cmd:
            _convert_imagemagick(im_cmd, src, dst)
        else:
            _convert_pillow(src, dst)
        return ('converted', None)
    except Exception as e:
        return ('failed', str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 標準入力でフォルダを質問
# ─────────────────────────────────────────────────────────────────────────────

def _ask_folder() -> pathlib.Path:
    """変換対象フォルダを標準入力で受け取る。バリデーション付き。"""
    while True:
        try:
            raw = input('変換対象のフォルダパスを入力してください: ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n中断しました。')
            sys.exit(0)

        if not raw:
            print('エラー: パスが空です。フォルダのパスを入力してください。')
            continue

        p = pathlib.Path(raw).expanduser().resolve()

        if not p.exists():
            print(f'エラー: 存在しないパスです: {p}')
            continue

        if not p.is_dir():
            print(f'エラー: ディレクトリではありません: {p}')
            continue

        return p


# ─────────────────────────────────────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='BMP → TIFF (LZW) 一括変換ツール。BMP は削除しません。',
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.set_defaults(recursive=True)
    parser.add_argument(
        '--no-recursive', dest='recursive', action='store_false',
        help='サブディレクトリを再帰処理しない (デフォルト: 再帰あり)',
    )
    parser.add_argument(
        '--overwrite', action='store_true',
        help='既存の TIFF ファイルを上書きする (デフォルト: スキップ)',
    )
    parser.add_argument(
        '--dryRun', action='store_true',
        help='実際に変換せず、処理内容だけ表示する',
    )
    parser.add_argument(
        '--jobs', type=int, default=2, metavar='N',
        help='並列変換数 (デフォルト: 2)\nNAS 環境では 1 を推奨',
    )
    parser.add_argument(
        '--ext', choices=['tif', 'tiff'], default='tif',
        help='出力ファイルの拡張子 (デフォルト: tif)',
    )
    parser.add_argument(
        '--dst', metavar='DIR', default=None,
        help='出力先ディレクトリ\n省略時は入力と同じ場所。指定時はディレクトリ構造を維持して配置する',
    )
    args = parser.parse_args()

    # ── 変換エンジン確認 ──────────────────────────────────────────────────────
    im_cmd = _detect_imagemagick()
    has_pillow = _detect_pillow()

    if not im_cmd and not has_pillow:
        print(
            'エラー: ImageMagick も Pillow も見つかりません。\n'
            'どちらかをインストールしてください:\n'
            '  sudo apt install imagemagick\n'
            '  pip install pillow',
            file=sys.stderr,
        )
        sys.exit(1)

    if im_cmd:
        print(f'変換エンジン: ImageMagick ({im_cmd})')
    else:
        print('変換エンジン: Pillow (tiff_lzw)')

    # ── フォルダを標準入力で受け取る ─────────────────────────────────────────
    src_root = _ask_folder()

    # ── 出力先ディレクトリ解決 ────────────────────────────────────────────────
    dst_root: Optional[pathlib.Path] = None
    if args.dst:
        dst_root = pathlib.Path(args.dst).expanduser().resolve()
        dst_root.mkdir(parents=True, exist_ok=True)

    # ── BMP ファイル収集 ──────────────────────────────────────────────────────
    print(f'\n{src_root} をスキャン中...')
    bmp_files = _collect_bmp(src_root, args.recursive)

    if not bmp_files:
        print('BMP ファイルが見つかりませんでした。終了します。')
        return

    print(f'{len(bmp_files)} 件の BMP ファイルを検出しました。\n')

    if args.dryRun:
        print('【dryRun モード】ファイルの書き込みは行いません。\n')

    # ── タスクリスト構築 ──────────────────────────────────────────────────────
    tasks: List[Tuple[pathlib.Path, pathlib.Path]] = [
        (src, _output_path(src, src_root, dst_root, args.ext))
        for src in bmp_files
    ]
    total = len(tasks)

    # ── 変換実行 ─────────────────────────────────────────────────────────────
    counts = {
        'converted': 0,
        'skipped': 0,
        'failed': 0,
        'would_convert': 0,
        'would_skip': 0,
    }
    failures: List[Tuple[pathlib.Path, str]] = []
    done = 0
    print_lock = threading.Lock()
    jobs = max(1, args.jobs)

    def submit_one(index: int, src: pathlib.Path, dst: pathlib.Path):
        status, detail = _process_file(
            src, dst,
            overwrite=args.overwrite,
            dry_run=args.dryRun,
            im_cmd=im_cmd,
        )
        return index, status, detail, src, dst

    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {
                pool.submit(submit_one, i + 1, src, dst): (src, dst)
                for i, (src, dst) in enumerate(tasks)
            }
            for future in as_completed(futures):
                idx, status, detail, src, dst = future.result()
                done += 1
                counts[status] += 1

                with print_lock:
                    prefix = f'[{done}/{total}]'
                    if status == 'converted':
                        print(f'{prefix} OK       {src}')
                        print(f'           → {dst}')
                    elif status == 'skipped':
                        print(f'{prefix} skip     {src}')
                    elif status == 'failed':
                        failures.append((src, detail or '不明なエラー'))
                        print(f'{prefix} FAILED   {src}')
                        print(f'           reason: {detail}')
                    elif status == 'would_convert':
                        print(f'{prefix} [{detail}] {src}')
                        print(f'           → {dst}')
                    elif status == 'would_skip':
                        print(f'{prefix} [skip]   {src}')

    except KeyboardInterrupt:
        print('\n\n中断されました（途中の TIFF は .tmp のまま残る可能性があります）。')

    # ── サマリ ────────────────────────────────────────────────────────────────
    sep = '─' * 60
    print(f'\n{sep}')
    print('処理結果サマリ')
    print(sep)
    if args.dryRun:
        print(f'  変換予定   : {counts["would_convert"]}')
        print(f'  スキップ予定: {counts["would_skip"]}')
    else:
        print(f'  変換成功   : {counts["converted"]}')
        print(f'  スキップ   : {counts["skipped"]}')
        print(f'  失敗       : {counts["failed"]}')

    if failures:
        print('\n失敗したファイル:')
        for src, msg in failures:
            print(f'  {src}')
            print(f'    {msg}')

    print(sep)

    if counts['failed'] > 0:
        sys.exit(2)


if __name__ == '__main__':
    main()
