import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { FileText, Download, Calendar, User, FolderArchive, Eye } from 'lucide-react';

const PDFs = () => {
  const { token, API } = useAuth();
  const [pdfs, setPdfs] = useState([]);
  const [batches, setBatches] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPDFs();
  }, []);

  const fetchPDFs = async () => {
    try {
      const [pdfsResponse, batchesResponse] = await Promise.all([
        axios.get(`${API}/pdfs/list`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/batches/list`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);

      setPdfs(pdfsResponse.data.pdfs);
      
      // Crear un mapa de batches por ID
      const batchMap = {};
      batchesResponse.data.batches.forEach(batch => {
        batchMap[batch.id] = batch;
      });
      setBatches(batchMap);
    } catch (error) {
      toast.error('Error al cargar PDFs');
    } finally {
      setLoading(false);
    }
  };

  const downloadPDF = async (pdf) => {
    try {
      const response = await axios.get(`${API}/pdfs/${pdf.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', pdf.filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('PDF descargado exitosamente');
    } catch (error) {
      toast.error('Error al descargar PDF');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / 1024 / 1024).toFixed(2) + ' MB';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-zinc-500">Cargando PDFs consolidados...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="pdfs-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold text-zinc-900 tracking-tight">PDFs Consolidados</h1>
        <p className="text-zinc-500 mt-2">Documentos de pago consolidados listos para descargar</p>
      </div>

      {pdfs.length === 0 ? (
        <Card className="border-zinc-200">
          <CardContent className="py-12 text-center">
            <FileText size={48} className="mx-auto text-zinc-300 mb-3" />
            <p className="text-zinc-500 mb-2">No hay PDFs consolidados generados</p>
            <p className="text-sm text-zinc-400">
              Crea un lote de documentos y genera un PDF consolidado para verlos aquí
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {pdfs.map((pdf) => {
            const batch = batches[pdf.batch_id];
            const numDocs = batch?.documentos?.length || 0;
            
            return (
              <Card key={pdf.id} className="border-zinc-200 hover:border-zinc-300 transition-all hover:shadow-md">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-xl flex items-center gap-2 mb-2">
                        <FileText size={24} className="text-emerald-600" />
                        <span className="truncate">{pdf.filename}</span>
                      </CardTitle>
                      <CardDescription className="flex items-center gap-2">
                        <FolderArchive size={14} />
                        Lote {pdf.batch_id.substring(0, 8)}
                      </CardDescription>
                    </div>
                    <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200">
                      <Eye size={12} className="mr-1" />
                      Listo
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-4">
                  {/* Información del PDF */}
                  <div className="grid grid-cols-2 gap-3 p-4 bg-zinc-50 rounded-lg border border-zinc-200">
                    <div>
                      <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">
                        Documentos
                      </p>
                      <p className="text-lg font-bold text-zinc-900 tabular-nums">{numDocs}</p>
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">
                        Tamaño
                      </p>
                      <p className="text-lg font-bold text-zinc-900 tabular-nums">
                        {formatFileSize(pdf.file_size)}
                      </p>
                    </div>
                  </div>

                  {/* Metadata */}
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2 text-zinc-600">
                      <Calendar size={14} className="text-zinc-400" />
                      <span>Generado: {new Date(pdf.created_at).toLocaleString('es-ES', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}</span>
                    </div>
                    <div className="flex items-center gap-2 text-zinc-600">
                      <User size={14} className="text-zinc-400" />
                      <span>Creado por usuario</span>
                    </div>
                  </div>

                  {/* Contenido del lote */}
                  {batch && (
                    <div className="pt-3 border-t border-zinc-200">
                      <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-2">
                        Contenido del PDF
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {['Comprobante Egreso', 'Cuenta Por Pagar', 'Factura', 'Soporte Pago']
                          .slice(0, numDocs)
                          .map((doc, idx) => (
                            <Badge key={idx} variant="outline" className="text-xs border-zinc-300 text-zinc-600">
                              {doc}
                            </Badge>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Botón de descarga */}
                  <Button
                    onClick={() => downloadPDF(pdf)}
                    className="w-full bg-zinc-900 hover:bg-zinc-800 text-white shadow-sm"
                    data-testid={`download-pdf-${pdf.id}`}
                  >
                    <Download size={18} className="mr-2" />
                    Descargar PDF
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Info Card */}
      {pdfs.length > 0 && (
        <Card className="border-zinc-200 bg-zinc-50">
          <CardContent className="p-6">
            <div className="flex gap-4 items-start">
              <div className="w-10 h-10 rounded-lg bg-zinc-900 flex items-center justify-center flex-shrink-0">
                <FileText size={20} className="text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-zinc-900 mb-1">Sobre los PDFs Consolidados</h3>
                <p className="text-sm text-zinc-600 leading-relaxed">
                  Cada PDF consolidado contiene documentos relacionados ordenados según el flujo de pago: 
                  Comprobante de Egreso → Cuenta Por Pagar → Factura → Soporte de Pago. 
                  Todos los documentos están respaldados en la base de datos y pueden ser descargados en cualquier momento.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default PDFs;
