import requests
import os
import openwakeword

base = os.path.join(os.path.dirname(openwakeword.__file__), 'resources', 'models')
os.makedirs(base, exist_ok=True)

files = [
    'embedding_model.onnx',
    'melspectrogram.onnx',
    'alexa_v0.1.onnx',
]

base_url = 'https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/'

for f_name in files:
    out = os.path.join(base, f_name)
    if not os.path.exists(out):
        print(f'Downloading {f_name}...')
        try:
            r = requests.get(base_url + f_name, stream=True)
            r.raise_for_status()
            with open(out, 'wb') as fp:
                for chunk in r.iter_content(chunk_size=8192):
                    fp.write(chunk)
            print(f'Saved: {out}')
        except Exception as e:
            print(f'Failed to download {f_name}: {e}')
    else:
        print(f'Already exists: {f_name}')

print('\nFinal file list in models directory:')
print(os.listdir(base))
