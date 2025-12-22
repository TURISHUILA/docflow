import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']

async def export_pdfs():
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    # Obtener todos los PDFs consolidados
    pdfs = await db.consolidated_pdfs.find({}, {"_id": 0}).to_list(100)
    
    if not pdfs:
        print("No hay PDFs consolidados en la base de datos")
        return
    
    # Crear directorio de exportación
    export_dir = "/tmp/pdfs_exportados"
    os.makedirs(export_dir, exist_ok=True)
    
    print(f"\n✓ Exportando {len(pdfs)} PDF(s) consolidado(s)...\n")
    
    for pdf in pdfs:
        filename = pdf['filename']
        pdf_data = pdf.get('pdf_data')
        
        if pdf_data:
            output_path = os.path.join(export_dir, filename)
            with open(output_path, 'wb') as f:
                f.write(pdf_data)
            
            file_size = len(pdf_data)
            print(f"✓ Exportado: {filename}")
            print(f"  - Tamaño: {file_size / 1024:.2f} KB")
            print(f"  - Ubicación: {output_path}")
            print(f"  - Lote: {pdf['batch_id']}")
            print(f"  - Creado: {pdf['created_at']}")
            print()
    
    print(f"\n📂 Todos los PDFs exportados a: {export_dir}\n")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(export_pdfs())
