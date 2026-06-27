# 🏷️ Data Labeling Classroom Tool

An interactive Streamlit app for teaching the challenges of data labeling in AI/ML courses.

## What it does

- **Instructor** uploads images and configures labels + timer duration
- A **QR code** and session code let students join on their phones/laptops
- **Students** label the current image from a dropdown before the timer runs out
- The instructor's screen shows a **live bar chart** of label distribution + discussion prompts

---

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open `http://localhost:8501` (instructor) and `http://localhost:8501/?role=student` (student).

---

## Deploying to Streamlit Community Cloud (free)

1. **Fork / push** this repo to your GitHub account.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app** → select your repo → set **Main file path** to `app.py` → Deploy.
4. Once deployed, you get a public URL like `https://your-app.streamlit.app`.
5. In the instructor dashboard, paste that URL into the **"Public URL"** field under *Student Access* so the QR code updates automatically.
6. Students scan the QR or go to `https://your-app.streamlit.app/?role=student`.

> **Note:** Streamlit Community Cloud runs a single instance, so the JSON state file is shared across all connections — perfect for a single classroom session.

---

## How to Use in Class

### Instructor
1. Open the app → **Setup tab**: upload images, configure labels, set timer.
2. **Session Control tab**: click *Start Voting* — the QR code and 4-letter session code appear.
3. Students scan and join. Watch the live timer and response count.
4. When timer ends (or you click *End & Show Results*), the bar chart appears on the **Results tab**.
5. Click *Next Image* to advance, or *New Session* to reset.

### Students
1. Scan the QR code (or type the URL) on their phone/laptop.
2. Enter their name and the 4-letter session code.
3. See the image and pick a label from the dropdown.
4. Submit before the timer runs out — they can change their answer until then.
5. After voting ends, results and a discussion prompt appear.

---

## Configuration Options

| Setting | Default | Range |
|---|---|---|
| Timer duration | 30 s | 10–300 s |
| Labels | Cat, Dog, Car… | Any list, one per line |
| Images | — | JPG, PNG, WEBP, GIF |

---

## File Structure

```
app.py                  ← Main Streamlit application
requirements.txt        ← Python dependencies
.streamlit/config.toml  ← Theme and server config
uploaded_images/        ← Created at runtime to store uploads
labeling_state.json     ← Created at runtime to share state
```

---

## Tips for Teaching

- Use **ambiguous images** (e.g. a hot dog that could be "food" or "object") to provoke disagreement.
- High disagreement → discuss **inter-annotator agreement**, **label guidelines**, and **edge cases**.
- High agreement → ask: *Is the label actually correct? What did you assume?*
- Try the same image with **different label sets** to show how schema design affects quality.
