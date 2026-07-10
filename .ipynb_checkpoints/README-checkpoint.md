# Truce

##  AMD Notebook Setup Guide (for Hackathon Judges)

This guide walks through the exact steps to run **Truce** inside the AMD Developer Cloud notebook environment.

---

###  Prerequisites (Before You Start)

- You have **registered your team** on [lablab.ai](https://lablab.ai) (even solo participants must create a team).
- Your team has been **allocated an AMD GPU pod** (allow up to 24 hours after registration).
- You can access the Jupyter environment at **`notebooks.amd.com/hackathon`**.
- You have **accepted Google's Gemma license** on Hugging Face:  
  [huggingface.co/google/gemma-2-2b-it](https://huggingface.co/google/gemma-2-2b-it) – click "Agree and access repository".

---

### 1. Clone the Repository

Open a terminal in the notebook (Jupyter → New → Terminal) and run:


> **Note:** If you get an SSL certificate error, use:  
> `git -c http.sslVerify=false clone <clone link>`

---

### 2. Create and Activate a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

Your prompt should now show `(venv)`.
ENSURE KERNAL IS THIS VENV AND NOT DEFAULT
---

### 3. Install Dependencies

#### Step 3a – Install PyTorch for ROCm (AMD GPU)

```bash
pip install torch --index-url https://download.pytorch.org/whl/rocm6.2 --no-cache-dir
```

#### Step 3b – Install the remaining packages

Ensure you have a `requirements.txt` file (included in the repo) and run:

```bash
pip install -r requirements.txt --no-cache-dir
```

> If `requirements.txt` is missing, you can install the essentials manually:  
> `pip install transformers accelerate huggingface_hub safetensors bitsandbytes python-dotenv requests supabase-python streamlit`

---

### 4. Configure Environment Variables

Copy the example file:

```bash
cp .env.example .env
```

Open `.env` (using the Jupyter file browser or `nano .env`) and fill in your credentials- refer to env example
---

### 5. Authenticate with Hugging Face

To download the Gemma model weights, you need to log in:

```bash
huggingface-cli login --token hf_xxxxxxxxxxxxxxxxxxxx
```

(If `huggingface-cli` isn't found, run `pip install huggingface_hub` first.)

---

### 6. Verify GPU Access and Model Loading

Run a quick test to confirm PyTorch sees the AMD GPU:

```bash
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

**Expected output:** `True AMD Raydeon` (or similar).

Then test that Gemma loads correctly (this will download ~5GB of weights once):

```python
python -c "
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
model = AutoModelForCausalLM.from_pretrained('google/gemma-2-2b-it', dtype=torch.bfloat16, device_map='cuda')
tok = AutoTokenizer.from_pretrained('google/gemma-2-2b-it')
print('✅ Gemma loaded on AMD GPU')
"
```

---

### 7. Run the Backend Smoke Tests

To verify the whole pipeline works (including database and LLM calls):

```bash
python run_test.py
```

If tests pass, your environment is fully functional.

---

### 8. Launch the Application (Streamlit UI)

Start the web interface:

```bash
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```

The notebook will display a public URL (e.g., `https://xxxx-8501.xxxx.amd.com`). Open that in a browser to interact with the app.

---

### 9. (Optional) Test the AMD Local Rate Ranking

You can manually test the local Gemma ranking function:

```bash
python -c "
from tools.rate_ranking import rank_rate
result = rank_rate('your-project-id', 50.0, 'Python Developer')
print(result)
"
```

You should see a JSON response with `score`, `verdict`, and `reasoning`.

---

### Capturing Proof of AMD GPU Usage

During the hackathon, it's important to prove you actually used the AMD hardware. While the model is loaded (or during a `rank_rate()` call), open a **second terminal** and run:

```bash
watch -n 1 rocm-smi
```

Screenshot the terminal showing:
- **Before:** GPU utilisation near 0%.
- **During:** VRAM% and GPU% climbing when Gemma is running.

Also capture the output of:

```bash
python -c "import torch; print(torch.cuda.get_device_name(0))"
```

This proves inference is happening on the AMD Instinct GPU.

---

### 🔁 Resetting or Restarting

If you need to start fresh (e.g., after a crash or power cycle), just re‑run the steps above. The cached model weights will be reused if you mount `~/.cache/huggingface` (or they'll be re‑downloaded).

---

### Troubleshooting Common Issues

| Issue | Solution |
| :--- | :--- |
| `ModuleNotFoundError: No module named 'torch'` | Install PyTorch with the ROCm index URL (Step 3a). |
| `torch.cuda.is_available()` returns `False` | Your venv might be using a CPU‑only torch. Re‑install from the ROCm index. |
| Hugging Face download fails with 403 | You haven't accepted the Gemma license or your HF token is invalid. |
| `.env` variables not loading | Check syntax (no spaces, no quotes). Use `cat .env` to verify. |
| `git pull` SSL certificate errors | Use `git -c http.sslVerify=false pull` or install `ca-certificates` with `apt-get update && apt-get install ca-certificates -y`. |
| Streamlit doesn't start | Ensure port 8501 is free; try a different port with `--server.port=8502`. |

---
### 📝 Notes for Judges

- The app's primary LLM is **Fireworks AI** (`gpt-oss-20b`) with an **automatic fallback to Groq**.
- The **AMD local ranking** is a separate module (`tools/rate_ranking.py`) that scores rates using **Gemma 2 2B** on the AMD GPU, proving hardware utilisation.

---

