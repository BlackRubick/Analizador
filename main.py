
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
import numpy as np
import cv2
from typing import Dict
from hernandez_corvo import apply_hernandez_corvo
from largest_contour import largest_contour
from preprocessing import preprocess_foot_image
import io
from fastapi.middleware.cors import CORSMiddleware
from knee_api import router as knee_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(knee_router)

@app.post("/analyze-foot/")
def analyze_foot(file: UploadFile = File(...)):
    image_bytes = file.file.read()
    npimg = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse(status_code=400, content={"error": "No se pudo leer la imagen"})
    try:
        steps = preprocess_foot_image(img)
        contour = largest_contour(steps["clean"], min_area_ratio=0.01, max_area_ratio=0.8)
        if contour is None:
            return JSONResponse(status_code=422, content={"error": "No se detectó contorno de pie"})
        hc_result, widths_info = apply_hernandez_corvo(steps["clean"], contour)
        PX_TO_CM = 60.0 / 1600.0
        x_width_cm = hc_result.x_width * PX_TO_CM
        y_width_cm = hc_result.y_width * PX_TO_CM
        annotated = img.copy()
        x_row = widths_info["x_row"]
        x_min, x_max = widths_info["x_min"], widths_info["x_max"]
        cv2.line(annotated, (x_min, x_row), (x_max, x_row), (0, 255, 0), 3)
        cv2.putText(annotated, f"X: {x_width_cm:.2f} cm", (x_min + 5, x_row - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        y_row = widths_info["y_row"]
        cv2.line(annotated, (x_min, y_row), (x_max, y_row), (0, 255, 255), 3)
        cv2.putText(annotated, f"Y: {y_width_cm:.2f} cm", (x_min + 5, y_row - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.drawContours(annotated, [contour], -1, (255, 0, 255), 2)
        _, buffer = cv2.imencode('.png', annotated)
        import base64
        annotated_b64 = base64.b64encode(buffer).decode('utf-8')
        return {
            "metrics": {
                "plantar_index": hc_result.index,
                "x_width_cm": x_width_cm,
                "y_width_cm": y_width_cm,
                "classification": hc_result.classification,
            },
            "images": {
                "annotated": f"data:image/png;base64,{annotated_b64}"
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
