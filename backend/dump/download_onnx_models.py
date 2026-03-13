import os
import requests
import openwakeword

model_dir = os.path.join(os.path.dirname(openwakeword.__file__), 'resources', 'models')
os.makedirs(model_dir, exist_ok=True)

models = [
    "embedding_model.onnx",
    "melspectrogram.onnx",
    "alexa_v0.1.onnx"
]

base_url = "https://github.com/dscripka/openWakeWord/raw/main/openwakeword/resources/models/"
hf_url = "https://huggingface.co/davidscripka/openwakeword_models/resolve/main/embedding_model.onnx"

for model in models:
    if model == "embedding_model.onnx":
        url = hf_url
    else:
        url = base_url + model
    target_path = os.path.join(model_dir, model)
    if os.path.exists(target_path):
        print(f"{model} already exists. Skipping.")
        continue
    
    print(f"Downloading {model} from {url}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully downloaded {model} to {target_path}")
    except Exception as e:
        print(f"Failed to download {model}: {e}")

print("\nFinal file list in models directory:")
print(os.listdir(model_dir))
