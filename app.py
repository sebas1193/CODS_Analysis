from flask import Flask, request, render_template, send_file
import pandas as pd
import matplotlib.pyplot as plt
import io
import os
import numpy as np
import zipfile
from datetime import datetime

# Función para procesar cada hoja (ciudad) de un archivo Excel
def process_sheet(sheet_name, file_path):
    df = pd.read_excel(file_path, sheet_name=sheet_name)

    df['Meta ODS'] = df['Meta ODS'].astype(str)
    df['Meta ODS'] = df['Meta ODS'].apply(lambda x: x.replace(',', '.') if ',' in x else x).str.rstrip(',')

    ods_dict = {}
    for meta in df['Meta ODS']:
        if meta != '<NA>' and meta.lower() != 'nan':
            ods_number = meta.split('.')[0]
            if f'ODS_{ods_number}' not in ods_dict:
                ods_dict[f'ODS_{ods_number}'] = set()
            ods_dict[f'ODS_{ods_number}'].add(meta)

    for i in range(1, 18):
        if f'ODS_{i}' not in ods_dict:
            ods_dict[f'ODS_{i}'] = []

    for key in ods_dict:
        ods_dict[key] = list(ods_dict[key])

    if 'ODS_nan' in ods_dict:
        del ods_dict['ODS_nan']

    filtered_df = df[df['Producto'] == 1]
    filtered_ods_dict = {}
    for meta in filtered_df['Meta ODS']:
        if pd.notna(meta) and meta.lower() != 'nan':
            ods_number = meta.split('.')[0]
            if f'ODS_{ods_number}' not in filtered_ods_dict:
                filtered_ods_dict[f'ODS_{ods_number}'] = set()
            filtered_ods_dict[f'ODS_{ods_number}'].add(meta)

    for i in range(1, 18):
        if f'ODS_{i}' not in filtered_ods_dict:
            filtered_ods_dict[f'ODS_{i}'] = []

    for key in filtered_ods_dict:
        filtered_ods_dict[key] = list(filtered_ods_dict[key])

    ods_propuesta_dict = {}
    meta_propuesta_dict = {}
    for meta in filtered_df['Meta ODS']:

        if pd.notna(meta) and meta.lower() != 'nan':
            ods_number = meta.split('.')[0]
            ods_key = f'ODS_{ods_number}_propuesta'
            meta_key = f'ODS_{ods_number}_meta_{meta}'
            if ods_key not in ods_propuesta_dict:
                ods_propuesta_dict[ods_key] = 0
            if meta_key not in meta_propuesta_dict:
                meta_propuesta_dict[meta_key] = 0
            ods_propuesta_dict[ods_key] += 1
            meta_propuesta_dict[meta_key] += 1

    for ods_number in range(1, 18):
        ods_key = f'ODS_{ods_number}_propuesta'
        if ods_key not in ods_propuesta_dict:
            ods_propuesta_dict[ods_key] = 0
        for meta in ods_dict[f'ODS_{ods_number}']:
            meta_key = f'ODS_{ods_number}_meta_{meta}'
            if meta_key not in meta_propuesta_dict:
                meta_propuesta_dict[meta_key] = 0

    return {
        "ODS_metas_doc": ods_dict,
        "ODS_metas_ciudad": filtered_ods_dict,
        "metas_total": sum(len(metas) for metas in filtered_ods_dict.values()),
        "ODS_propuesta": ods_propuesta_dict,
        "Meta_propuesta": meta_propuesta_dict
    }

# Función para generar las gráficas radiales (con o sin ODS 14)
def generar_grafica_radial(ciudad, data, incluir_ods14=True):
    ods_labels = [f'ODS {i}' for i in range(1, 18) if incluir_ods14 or i != 14]
    
    ods_metas_doc = data["ODS_metas_doc"]
    ods_metas_ciudad = data["ODS_metas_ciudad"]
    
    cumplimiento = []
    for i in range(1, 18):
        if not incluir_ods14 and i == 14:
            continue
        ods_key = f'ODS_{i}'
        total_metas = len(ods_metas_doc.get(ods_key, []))
        metas_cumplidas = len(ods_metas_ciudad.get(ods_key, []))
        porcentaje_cumplido = (metas_cumplidas / total_metas) * 100 if total_metas > 0 else 0
        cumplimiento.append(porcentaje_cumplido)
    
    angles = np.linspace(0, 2 * np.pi, len(ods_labels), endpoint=False).tolist()
    cumplimiento += cumplimiento[:1]
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    
    ax.fill(angles, cumplimiento, color='blue', alpha=0.25)
    ax.plot(angles, cumplimiento, color='blue', linewidth=2)
    
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'], fontsize=10, va='bottom')
    
    ax.set_ylim(0, 110)
    
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(ods_labels, fontsize=12, ha='center')
    
    for label in ax.get_xticklabels():
        label.set_fontsize(12)
        label.set_verticalalignment('top')
        label.set_y(label.get_position()[1] - 0.05)
    
    plt.title(f'Cumplimiento de Metas ODS en {ciudad} {"(sin ODS 14)" if not incluir_ods14 else ""}', size=20, color='Black', y=1.1)

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    return img

app = Flask(__name__)

@app.route('/')
def upload_file():
    return render_template('upload_drag.html')

@app.route('/process', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        return "No file part"
    
    file = request.files['file']
    
    if file.filename == '':
        return "No selected file"
    
    if file:
        results = {}
        xls = pd.ExcelFile(file)
        
        # Crear un archivo ZIP para almacenar todas las imágenes generadas
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Procesar cada hoja del archivo Excel
            for sheet in xls.sheet_names:
                results[sheet] = process_sheet(sheet, file)
                data = results[sheet]
                
                # Generar la gráfica con ODS 14
                img_con_ods14 = generar_grafica_radial(sheet, data, incluir_ods14=True)
                img_name_con_ods14 = f"con_ods14/{sheet}_grafica_con_ods14.png"
                zip_file.writestr(img_name_con_ods14, img_con_ods14.getvalue())

                # Generar la gráfica sin ODS 14
                img_sin_ods14 = generar_grafica_radial(sheet, data, incluir_ods14=False)
                img_name_sin_ods14 = f"sin_ods14/{sheet}_grafica_sin_ods14.png"
                zip_file.writestr(img_name_sin_ods14, img_sin_ods14.getvalue())

        # Preparar el archivo ZIP para su descarga
        zip_buffer.seek(0)
        zip_filename = f"graficas_ods_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=zip_filename)

if __name__ == '__main__':
    app.run(debug=True)
