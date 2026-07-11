"""
download_models.py

Run once at image build time (see Dockerfile) so the container never hits
the network for local model weights at runtime -- keeps startup fast and
the 10-minute runtime budget free for actual video processing.

Does NOT touch Fireworks -- those calls need a real API key which isn't
available at build time (and shouldn't be baked into the image anyway).
"""

import config


def main():
    if not config.ENABLE_AUDIO_PIPELINE:
        print("Audio pipeline disabled -- skipping model prefetch.")
        return

    print(f"Prefetching faster-whisper '{config.WHISPER_MODEL_SIZE}'...")
    from faster_whisper import WhisperModel

    WhisperModel(
        config.WHISPER_MODEL_SIZE,
        device="cpu",
        compute_type=config.WHISPER_COMPUTE_TYPE,
        download_root=config.HF_HOME,
    )

    if config.ENABLE_SOURCE_SEPARATION:
        print(f"Prefetching Demucs '{config.DEMUCS_MODEL}'...")
        from demucs.pretrained import get_model

        get_model(config.DEMUCS_MODEL)

    if config.ENABLE_BACKGROUND_CLASSIFICATION:
        print(f"Prefetching AST '{config.AST_MODEL_ID}'...")
        from transformers import pipeline

        pipeline(task="audio-classification", model=config.AST_MODEL_ID, device=-1)

    print("Model prefetch complete.")


if __name__ == "__main__":
    main()
