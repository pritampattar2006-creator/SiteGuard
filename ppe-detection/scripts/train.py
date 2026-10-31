"""Fine-tune YOLO on a prepared 3-class dataset.

Usage:
  python scripts/train.py                                   # original data, from the pretrained model
  python scripts/train.py --data data/ppe_merged/data.yaml --model weights/best.pt --epochs 30 --name ppe_v2

Best weights end up in runs/train/<name>/weights/best.pt
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/ppe3/data.yaml")
    parser.add_argument("--model", default="yolo11s.pt")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--imgsz", type=int, default=960)  # larger than 640 so distant workers stay visible
    parser.add_argument("--batch", type=int, default=-1)  # -1: largest batch that fits the GPU
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--name", default="ppe")
    parser.add_argument("--workers", type=int, default=4)  # fewer loader processes use less memory
    parser.add_argument("--lr0", type=float, default=None)  # a lower starting learning rate keeps what a model already knows when fine-tuning
    parser.add_argument("--time", type=float, default=None)  # hours; when set it replaces --epochs and the schedule fits the time
    args = parser.parse_args()

    from ultralytics import YOLO

    YOLO(args.model).train(
        data=args.data,
        imgsz=args.imgsz,
        epochs=args.epochs,
        time=args.time,
        **({"lr0": args.lr0} if args.lr0 else {}),
        batch=args.batch,
        workers=args.workers,
        project=str(ROOT / "runs" / "train"),  # absolute, so Ultralytics does not nest it under runs/detect
        name=args.name,
        exist_ok=True,
        patience=args.patience,
        hsv_v=0.5,  # stronger brightness variation for poor lighting
        degrees=5.0,
        mosaic=1.0,
    )


if __name__ == "__main__":  # required on Windows because of dataloader worker processes
    main()
