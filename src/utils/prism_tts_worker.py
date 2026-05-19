"""
Prism TTS helper process.

On Linux, importing and initializing Prism in the wx/GTK GUI process can clash
with GLib/GIO type registration.  This helper keeps Prism isolated in a plain
Python subprocess.
"""

import argparse
import json
import shutil
import subprocess
import sys
import time


def _load_prism():
    from prism import BackendId, Context, PrismError
    return BackendId, Context, PrismError


def _backend_can_announce(backend) -> bool:
    features = backend.features
    return features.supports_speak or features.supports_output


def _backend_is_available(backend) -> bool:
    return _backend_can_announce(backend)


def _create_backend(context, engine_name: str = ''):
    if engine_name:
        return context.create(context.id_of(engine_name))
    if sys.platform.startswith("linux"):
        from prism import BackendId
        errors = []
        for backend_id in (
            BackendId.ORCA,
            getattr(BackendId, "SPIEL", None),
            BackendId.SPEECH_DISPATCHER,
        ):
            if backend_id is None:
                continue
            try:
                return context.create(backend_id)
            except Exception as e:
                errors.append(f"{backend_id.name}: {e}")
        raise ValueError("No supported Linux Prism backend found: " + "; ".join(errors))
    return context.create_best()


def _registry_snapshot(context) -> str:
    names = []
    for idx in range(context.backends_count):
        try:
            names.append(context.name_of(context.id_of(idx)))
        except Exception as e:
            names.append(f"<backend {idx}: {e}>")
    return ", ".join(names) if names else "<empty>"


def _find_voice_index(PrismError, backend, voice_name: str):
    features = backend.features
    if not voice_name or not (
        features.supports_count_voices and
        features.supports_get_voice_name and
        features.supports_set_voice
    ):
        return None
    try:
        backend.refresh_voices()
    except PrismError:
        pass
    for idx in range(backend.voices_count):
        if backend.get_voice_name(idx) == voice_name:
            return idx
    return None


def _wait_for_backend_to_finish(PrismError, backend, text: str):
    features = backend.features
    if features.supports_is_speaking:
        deadline = time.monotonic() + 60.0
        startup_deadline = time.monotonic() + 2.0
        observed_speaking = False
        while time.monotonic() < deadline:
            try:
                speaking = backend.speaking
                observed_speaking = observed_speaking or speaking
                if not speaking and (observed_speaking or time.monotonic() >= startup_deadline):
                    return
            except PrismError:
                return
            time.sleep(0.05)
        return
    time.sleep(min(10.0, max(1.0, len(text) * 0.08)))


def list_engines():
    _BackendId, Context, _PrismError = _load_prism()
    context = Context()
    engines = []
    try:
        backend = _create_backend(context, '')
        if backend is not None and _backend_is_available(backend):
            label = backend.name or "Prism best backend"
            engines.append([label, ""])
    except Exception:
        pass
    if sys.platform.startswith("linux"):
        return engines
    for idx in range(context.backends_count):
        backend_id = context.id_of(idx)
        name = context.name_of(backend_id)
        try:
            backend = context.create(backend_id)
            if _backend_is_available(backend):
                engines.append([name, name])
        except Exception:
            pass
    return engines


def list_voices(engine_name: str):
    if sys.platform.startswith("linux") and not engine_name:
        return []
    _BackendId, Context, PrismError = _load_prism()
    context = Context()
    try:
        backend = _create_backend(context, engine_name)
        if backend is None or not _backend_is_available(backend):
            return []
        features = backend.features
        if not (
            features.supports_count_voices and
            features.supports_get_voice_name
        ):
            return []
        try:
            backend.refresh_voices()
        except PrismError:
            pass
        return [[backend.get_voice_name(idx), str(idx)] for idx in range(backend.voices_count)]
    except Exception:
        return []


def speak(config: dict):
    _BackendId, Context, PrismError = _load_prism()
    context = Context()
    try:
        backend = _create_backend(context, config.get("engine_name", ""))
    except Exception as e:
        if _speak_with_speech_dispatcher(config):
            return
        raise RuntimeError(
            f"{e}; Prism registry contains: {_registry_snapshot(context)}"
        ) from e
    features = backend.features

    rate = int(config.get("rate", 0))
    volume = int(config.get("volume", -1))
    voice_name = config.get("voice_name", "")
    text = config.get("text", "")

    if rate != 0 and features.supports_set_rate:
        backend.rate = max(0.0, min(1.0, rate / 100.0))
    if volume >= 0 and features.supports_set_volume:
        backend.volume = max(0.0, min(1.0, volume / 100.0))
    if voice_name:
        voice_idx = _find_voice_index(PrismError, backend, voice_name)
        if voice_idx is not None:
            backend.voice = voice_idx

    interrupt = not sys.platform.startswith("linux")

    if features.supports_braille and features.supports_output:
        backend.output(text, interrupt=interrupt)
    elif features.supports_speak:
        backend.speak(text, interrupt=interrupt)
    elif features.supports_output:
        backend.output(text, interrupt=interrupt)
    else:
        raise RuntimeError(f"Prism backend '{backend.name}' cannot speak or output text")

    _wait_for_backend_to_finish(PrismError, backend, text)


def _speak_with_speech_dispatcher(config: dict) -> bool:
    """Fallback for Linux builds where Prism lacks compiled Linux backends."""
    if not sys.platform.startswith("linux"):
        return False
    spd_say = shutil.which("spd-say")
    if not spd_say:
        return False
    text = config.get("text", "")
    if not text:
        return False
    command = [spd_say, "--wait"]
    volume = int(config.get("volume", -1))
    rate = int(config.get("rate", 0))
    if volume >= 0:
        command.extend(["--volume", str(max(-100, min(100, (volume * 2) - 100)))])
    if rate:
        command.extend(["--rate", str(max(-100, min(100, (rate * 2) - 100)))])
    command.append(text)
    subprocess.run(command, check=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("list-engines", "list-voices", "speak"))
    parser.add_argument("--engine", default="")
    parser.add_argument("--config", default="")
    args = parser.parse_args()

    if args.command == "list-engines":
        print(json.dumps(list_engines(), ensure_ascii=False))
    elif args.command == "list-voices":
        print(json.dumps(list_voices(args.engine), ensure_ascii=False))
    elif args.command == "speak":
        speak(json.loads(args.config))


if __name__ == "__main__":
    main()
