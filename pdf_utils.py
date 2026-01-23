import io
import fitz  # PyMuPDF

def extraer_texto_de_archivo(file_obj, filename: str) -> str:
    """
    Lee un archivo binario (PDF o TXT) y devuelve su texto.
    """
    try:
        texto_completo = ""
        
        # Si es PDF
        if filename.lower().endswith(".pdf"):
            # Leemos los bytes del archivo subido
            content = file_obj.read()
            # Abrimos con PyMuPDF desde memoria
            pdf_document = fitz.open(stream=content, filetype="pdf")
            
            for page in pdf_document:
                texto_completo += page.get_text() + "\n"
                
            pdf_document.close()
            
        # Si es TXT
        elif filename.lower().endswith(".txt"):
            content = file_obj.read()
            texto_completo = content.decode("utf-8", errors="ignore")
            
        # (Aquí podrías agregar soporte para .docx usando python-docx si quisieras)
        
        return texto_completo.strip()

    except Exception as e:
        print(f"Error leyendo archivo {filename}: {e}")
        return ""