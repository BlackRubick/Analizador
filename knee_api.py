from fastapi import APIRouter, File, UploadFile, Request
from fastapi.responses import StreamingResponse, JSONResponse
import io
import base64
import cv2
import numpy as np
import mediapipe as mp
import logging
from report_utils import generate_report_pdf

router = APIRouter()

# Endpoint para generar PDF de reporte
@router.post("/generate-report/")
async def generate_report(request: Request):
    try:
        data = await request.json()
        pdf_bytes = generate_report_pdf(data)
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers={
            "Content-Disposition": "attachment; filename=ReportePaciente.pdf"
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# -------- FUNCIONES --------
def angle_between_points(a, b, c):
    ba = np.array(a) - np.array(b)
    bc = np.array(c) - np.array(b)
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)
    if norm_ba == 0 or norm_bc == 0:
        raise ValueError("Vectores inválidos para cálculo de ángulo (norma cero)")
    cos_angle = np.dot(ba, bc) / (norm_ba * norm_bc)
    angle = np.arccos(np.clip(cos_angle, -1.0, 1.0))
    deg = np.degrees(angle)
    if np.isnan(deg):
        raise ValueError("Ángulo inválido (NaN)")
    return deg

class PoseDetector:
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(static_image_mode=True, min_detection_confidence=0.5)

    def detect(self, image):
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.pose.process(img_rgb)
        if not results.pose_landmarks:
            raise Exception("No landmarks")
        h, w = image.shape[:2]
        lm = results.pose_landmarks.landmark
        return {
            "left_hip": (int(lm[self.mp_pose.PoseLandmark.LEFT_HIP].x * w), int(lm[self.mp_pose.PoseLandmark.LEFT_HIP].y * h)),
            "left_knee": (int(lm[self.mp_pose.PoseLandmark.LEFT_KNEE].x * w), int(lm[self.mp_pose.PoseLandmark.LEFT_KNEE].y * h)),
            "left_ankle": (int(lm[self.mp_pose.PoseLandmark.LEFT_ANKLE].x * w), int(lm[self.mp_pose.PoseLandmark.LEFT_ANKLE].y * h)),
            "right_hip": (int(lm[self.mp_pose.PoseLandmark.RIGHT_HIP].x * w), int(lm[self.mp_pose.PoseLandmark.RIGHT_HIP].y * h)),
            "right_knee": (int(lm[self.mp_pose.PoseLandmark.RIGHT_KNEE].x * w), int(lm[self.mp_pose.PoseLandmark.RIGHT_KNEE].y * h)),
            "right_ankle": (int(lm[self.mp_pose.PoseLandmark.RIGHT_ANKLE].x * w), int(lm[self.mp_pose.PoseLandmark.RIGHT_ANKLE].y * h)),
            "right_shoulder": (int(lm[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].x * w), int(lm[self.mp_pose.PoseLandmark.RIGHT_SHOULDER].y * h)),
            "left_shoulder": (int(lm[self.mp_pose.PoseLandmark.LEFT_SHOULDER].x * w), int(lm[self.mp_pose.PoseLandmark.LEFT_SHOULDER].y * h)),
        }

# -------- ENDPOINTS --------

@router.post("/analyze-muscle-chain/")
def analyze_muscle_chain(file: UploadFile = File(...)):
    image_bytes = file.file.read()
    npimg = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse(status_code=400, content={"error": "Imagen inválida"})
    detector = PoseDetector()
    try:
        lm = detector.detect(img)
        # Calcular ángulos de toda la cadena posterior (tobillo, rodilla, cadera, hombro)
        # Se asume que angle_between_points(A, B, C) calcula el ángulo en B entre los segmentos AB y BC
        ang_left_knee = angle_between_points(lm["left_hip"], lm["left_knee"], lm["left_ankle"])
        ang_right_knee = angle_between_points(lm["right_hip"], lm["right_knee"], lm["right_ankle"])
        # Para cadera y hombro, necesitamos los puntos del hombro
        # Si no existen, devolver error más claro
        if not all(k in lm for k in ["left_hip", "left_shoulder", "right_hip", "right_shoulder"]):
            raise ValueError("No se detectaron hombros para análisis de cadena completa.")
        ang_left_hip = angle_between_points(lm["left_shoulder"], lm["left_hip"], lm["left_knee"])
        ang_right_hip = angle_between_points(lm["right_shoulder"], lm["right_hip"], lm["right_knee"])
        ang_left_ankle = angle_between_points(lm["left_knee"], lm["left_ankle"], (lm["left_ankle"][0], lm["left_ankle"][1]+100))
        ang_right_ankle = angle_between_points(lm["right_knee"], lm["right_ankle"], (lm["right_ankle"][0], lm["right_ankle"][1]+100))

        print("ANGULOS: Rodilla izq:", ang_left_knee, "Rodilla der:", ang_right_knee)
        print("ANGULOS: Cadera izq:", ang_left_hip, "Cadera der:", ang_right_hip)
        print("ANGULOS: Tobillo izq:", ang_left_ankle, "Tobillo der:", ang_right_ankle)

        if any(np.isnan(a) for a in [ang_left_knee, ang_right_knee, ang_left_hip, ang_right_hip, ang_left_ankle, ang_right_ankle]):
            raise ValueError("Ángulos inválidos (NaN)")

        # Rasgos descriptivos
        rasgos = [
            f"Ángulo rodilla derecha: {ang_right_knee:.1f}°",
            f"Ángulo cadera izquierda: {ang_left_hip:.1f}°",
            f"Ángulo cadera derecha: {ang_right_hip:.1f}°",
            f"Ángulo tobillo izquierdo: {ang_left_ankle:.1f}°",
            f"Ángulo tobillo derecho: {ang_right_ankle:.1f}°"
        ]

        # Clasificación extendida de cadenas miofasciales
        # (Reglas iniciales, puedes ajustar los umbrales y lógica según tu criterio clínico)
        chain = "Indeterminada"
        explanation = "No se pudo clasificar la cadena con los datos actuales."

        # Flexión: flexión marcada en rodillas y caderas
        if any(a < 160 for a in [ang_left_knee, ang_right_knee, ang_left_hip, ang_right_hip]):
            chain = "Cadena de flexión"
            explanation = "Se detecta flexión significativa en al menos una articulación principal (rodilla o cadera)."
        # Extensión: todos los ángulos principales muy extendidos
        elif all(a > 170 for a in [ang_left_knee, ang_right_knee, ang_left_hip, ang_right_hip]):
            chain = "Cadena de extensión"
            explanation = "Todas las articulaciones principales están en extensión."
        # Apertura: tobillos y caderas abiertas (ángulos grandes en cadera y tobillo)
        elif all(a > 170 for a in [ang_left_hip, ang_right_hip, ang_left_ankle, ang_right_ankle]) and any(a < 170 for a in [ang_left_knee, ang_right_knee]):
            chain = "Cadena de apertura"
            explanation = "Caderas y tobillos en apertura, rodillas con ligera flexión."
        # Cierre: tobillos y caderas cerradas (ángulos pequeños en cadera y tobillo)
        elif any(a < 160 for a in [ang_left_hip, ang_right_hip, ang_left_ankle, ang_right_ankle]):
            chain = "Cadena de cierre"
            explanation = "Caderas o tobillos en cierre (flexión o aducción marcada)."
        # Inspiración: todos los ángulos grandes (postura erguida, apertura general)
        elif all(a > 175 for a in [ang_left_knee, ang_right_knee, ang_left_hip, ang_right_hip, ang_left_ankle, ang_right_ankle]):
            chain = "Cadena de inspiración"
            explanation = "Postura global de apertura e inspiración (todos los ángulos grandes)."
        # Espiración: todos los ángulos pequeños (postura de cierre global)
        elif all(a < 160 for a in [ang_left_knee, ang_right_knee, ang_left_hip, ang_right_hip, ang_left_ankle, ang_right_ankle]):
            chain = "Cadena de espiración"
            explanation = "Postura global de cierre y espiración (todos los ángulos pequeños)."

        return {
            "chain": chain,
            "explanation": explanation,
            "rasgos": rasgos,
            "left_knee_angle": ang_left_knee,
            "right_knee_angle": ang_right_knee,
            "left_hip_angle": ang_left_hip,
            "right_hip_angle": ang_right_hip,
            "left_ankle_angle": ang_left_ankle,
            "right_ankle_angle": ang_right_ankle
        }
    except Exception as e:
        import traceback
        exc_type = type(e).__name__
        msg = str(e).strip()
        tb = traceback.format_exc()
        if not msg or msg == 'None':
            msg = "No se detectaron puntos de referencia o la imagen no es válida."
        explanation = f"[{exc_type}] {msg}\nTraceback: {tb}"
        return JSONResponse(
            status_code=500,
            content={
                "chain": None,
                "explanation": explanation,
                "rasgos": [],
                "left_knee_angle": None,
                "right_knee_angle": None,
                "left_hip_angle": None,
                "right_hip_angle": None,
                "left_ankle_angle": None,
                "right_ankle_angle": None
            }
        )

def draw_knee_frontal(image: np.ndarray):
    annotated = image.copy()
    detector = PoseDetector()
    try:
        landmarks = detector.detect(image)
    except Exception:
        cv2.putText(annotated, "No se detectaron puntos de referencia", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return annotated, None, None
    # Puntos clave
    l_ankle = landmarks["left_ankle"]
    l_knee = landmarks["left_knee"]
    l_hip = landmarks["left_hip"]
    r_ankle = landmarks["right_ankle"]
    r_knee = landmarks["right_knee"]
    r_hip = landmarks["right_hip"]
    # Punto entrepierna (más realista: mitad vertical entre caderas y rodillas, centrado entre rodillas)
    crotch_x = int((l_knee[0] + r_knee[0]) / 2)
    crotch_y = int(( (l_hip[1] + r_hip[1]) / 2 + (l_knee[1] + r_knee[1]) / 2 ) / 2)
    crotch = (crotch_x, crotch_y)
    # Dibuja puntos anatómicos
    for pt in [l_ankle, l_knee, l_hip, r_ankle, r_knee, r_hip, crotch]:
        cv2.circle(annotated, pt, 8, (0, 255, 255), -1)
    # Dibuja líneas: cadera→rodilla, rodilla→tobillo
    cv2.line(annotated, l_hip, l_knee, (0, 255, 0), 3)
    cv2.line(annotated, l_knee, l_ankle, (255, 0, 0), 3)
    cv2.line(annotated, l_hip, l_knee, (0, 255, 0), 3)
    cv2.line(annotated, l_knee, l_ankle, (255, 0, 0), 3)
    cv2.line(annotated, r_hip, r_knee, (0, 255, 0), 3)
    cv2.line(annotated, r_knee, r_ankle, (255, 0, 0), 3)
    cv2.line(annotated, l_knee, crotch, (0, 0, 255), 7)
    cv2.line(annotated, r_knee, crotch, (0, 0, 255), 7)
    cv2.circle(annotated, crotch, 16, (0, 0, 255), -1)
    cv2.putText(annotated, 'Entrepierna', (crotch[0]-40, crotch[1]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
    # Ángulo tibiofemoral izquierdo y derecho (cadera-rodilla-entrepierna)
    angle_left = angle_between_points(l_hip, l_knee, crotch)
    angle_right = angle_between_points(r_hip, r_knee, crotch)
    # Mostrar ángulos
    cv2.putText(annotated, f"Ang Izq: {angle_left:.1f}", (l_knee[0]-40, l_knee[1]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)
    cv2.putText(annotated, f"Ang Der: {angle_right:.1f}", (r_knee[0]-40, r_knee[1]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,0), 2)
    # Clasificación simple
    avg_angle = (angle_left + angle_right) / 2
    classification = "Normal" if 170 <= avg_angle <= 180 else "Valgo/Varo"
    return annotated, avg_angle, classification

def draw_knee_sagittal(image: np.ndarray):
    annotated = image.copy()
    detector = PoseDetector()
    try:
        landmarks = detector.detect(image)
    except Exception:
        cv2.putText(annotated, "No se detectaron puntos de referencia", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        return annotated, None, None

    # Selección automática del lado más visible
    left_vis = sum([landmarks.get(k, (0,0))[0] for k in ["left_hip", "left_knee", "left_ankle"]])
    right_vis = sum([landmarks.get(k, (0,0))[0] for k in ["right_hip", "right_knee", "right_ankle"]])
    side = "left" if left_vis >= right_vis else "right"

    hip = landmarks[f"{side}_hip"]
    knee = landmarks[f"{side}_knee"]
    ankle = landmarks[f"{side}_ankle"]

    # Colores
    line_color = (255, 140, 0)   # naranja
    point_color = (0, 0, 0)
    angle_bg = (0, 255, 255)     # amarillo fuerte para máximo contraste

    # Puntos
    for pt in [hip, knee, ankle]:
        cv2.circle(annotated, pt, 6, point_color, -1)

    # Líneas
    cv2.line(annotated, hip, knee, line_color, 3)
    cv2.line(annotated, knee, ankle, line_color, 3)

    # Ángulo
    ang = angle_between_points(hip, knee, ankle)

    # Texto del ángulo (más pequeño y arriba de la rodilla)
    angle_text = f"{ang:.1f}°"
    (tw, th), _ = cv2.getTextSize(angle_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
    text_pos = (knee[0] - tw // 2, knee[1] - 28)
    # Fondo pequeño y discreto

    # ...existing code...
    cv2.putText(
        annotated,
        angle_text,
        (text_pos[0], text_pos[1] + th),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2
    )

    # Clasificación clínica
    if 175 <= ang <= 185:
        classification = "Normal"
    elif ang < 175:
        classification = "Genu Flexum"
    elif ang > 185:
        classification = "Genu Recurvatum"
    else:
        classification = "Límite / indeterminado"

    return annotated, ang, classification

@router.post("/analyze-knee/frontal/")
def analyze_knee_frontal(file: UploadFile = File(...)):
    image_bytes = file.file.read()
    npimg = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse(status_code=400, content={"error": "No se pudo leer la imagen"})
    annotated, angle, classification = draw_knee_frontal(img)
    _, buffer = cv2.imencode('.png', annotated)
    annotated_b64 = base64.b64encode(buffer).decode('utf-8')
    return {
        "metrics": {
            "plane": "frontal",
            "knee_angle_deg": angle,
            "classification": classification,
        },
        "images": {
            "annotated": f"data:image/png;base64,{annotated_b64}"
        }
    }

@router.post("/analyze-knee/sagittal/")
def analyze_knee_sagittal(file: UploadFile = File(...)):
    image_bytes = file.file.read()
    npimg = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse(status_code=400, content={"error": "No se pudo leer la imagen"})
    annotated, angle, classification = draw_knee_sagittal(img)
    _, buffer = cv2.imencode('.png', annotated)
    annotated_b64 = base64.b64encode(buffer).decode('utf-8')
    return {
        "metrics": {
            "plane": "sagittal",
            "knee_angle_deg": angle,
            "classification": classification,
        },
        "images": {
            "annotated": f"data:image/png;base64,{annotated_b64}"
        }
    }
