import cv2
import numpy as np
import zipfile
import os
import sys
import argparse
from pathlib import Path
from datetime import timedelta
from typing import Callable


def format_timestamp(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}h{minutes:02d}m{secs:02d}s{millis:03d}ms"


def compute_frame_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
    return float(np.mean(cv2.absdiff(gray1, gray2)))


def process_video(
    video_path: str,
    output_path: str,
    threshold: float = 5.0,
    min_interval_sec: float = 0.5,
    image_format: str = "png",
    log_fn: Callable[[str], None] = print,
) -> int:
    """
    Processa o vídeo e escreve cada frame detectado diretamente no ZIP.
    Retorna o total de frames capturados.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Não foi possível abrir o vídeo: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    log_fn(f"FPS: {fps:.2f} | Frames: {total_frames} | Duração: {format_timestamp(duration)}")
    log_fn(f"Threshold: {threshold} | Intervalo mínimo: {min_interval_sec}s")

    count = 0
    prev_frame = None
    last_captured_time = -min_interval_sec
    frame_idx = 0

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            timestamp = frame_idx / fps if fps > 0 else 0
            should_capture = False

            if prev_frame is None:
                should_capture = True
                log_fn(f"[{format_timestamp(timestamp)}] Primeiro frame capturado")
            else:
                diff = compute_frame_diff(prev_frame, frame)
                if diff >= threshold and (timestamp - last_captured_time) >= min_interval_sec:
                    should_capture = True
                    log_fn(f"[{format_timestamp(timestamp)}] Mudança detectada (diff={diff:.2f})")

            if should_capture:
                count += 1
                filename = f"Screen{count:04d}.{image_format}"
                success, encoded = cv2.imencode(f".{image_format}", frame)
                if success:
                    zf.writestr(filename, encoded.tobytes())
                    log_fn(f"  >> {filename}")
                last_captured_time = timestamp

            prev_frame = frame
            frame_idx += 1

            if frame_idx % 500 == 0:
                pct = (frame_idx / total_frames * 100) if total_frames > 0 else 0
                log_fn(f"... {frame_idx}/{total_frames} frames ({pct:.1f}%)")

    cap.release()

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    log_fn(f"ZIP gerado: {output_path} ({size_mb:.1f} MB, {count} imagens)")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrai frames de mudança de tela de um vídeo .mp4 e salva em ZIP."
    )
    parser.add_argument("video", help="Caminho para o arquivo .mp4")
    parser.add_argument("-o", "--output", help="Caminho do ZIP de saída")
    parser.add_argument("-t", "--threshold", type=float, default=5.0)
    parser.add_argument("-i", "--interval", type=float, default=0.5)
    parser.add_argument("-f", "--format", choices=["png", "jpg"], default="png")

    args = parser.parse_args()

    if not os.path.isfile(args.video):
        print(f"Erro: arquivo não encontrado: {args.video}")
        sys.exit(1)

    output_path = args.output or str(
        Path(args.video).parent / f"{Path(args.video).stem}_screens.zip"
    )

    print("=== Video Screen Capture ===\n")
    total = process_video(args.video, output_path, args.threshold, args.interval, args.format)
    print(f"\nConcluído: {total} telas capturadas.")


if __name__ == "__main__":
    main()
