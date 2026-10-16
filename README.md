# AI Object Finder

AI Object Finder is a robot project combining:

- IoT: ESP32 + motors + sensors + ESP32-CAM
- ML: object detection + visual feature similarity
- Cloud/Web: dashboard + image upload + Flask API

## Current working stage

1. Open `index.html` in a browser.
2. Start the Flask server.
3. Upload or take a reference image.
4. The image is sent to Flask.
5. Flask saves it inside `backend/uploads/`.

## Start backend

Open a terminal inside the `backend` folder:

```bash
pip install -r requirements.txt
python app.py
```

Then open:

http://127.0.0.1:5000/

You should see:

{
  "status": "online",
  "message": "AI Object Finder ML Server is running"
}

## Frontend

Open `index.html`.

The current "Object Found" result is still a temporary simulation.

Next stage:
- install ML dependencies
- add YOLO
- add feature embeddings
- add similarity matching
- replace the simulation with real ML inference
- connect ESP32-CAM
- connect robot movement commands
