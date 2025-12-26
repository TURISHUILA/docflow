import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { FileText, Download, Calendar, User, FolderArchive, Eye, X, Maximize2 } from 'lucide-react';

const PDFs = () => {
  const { token, API } = useAuth();
  const [pdfs, setPdfs] = useState([]);
  const [batches, setBatches] = useState({});
  const [loading, setLoading] = useState(true);
  const [previewPdf, setPreviewPdf] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);

  useEffect(() => {
    fetchPDFs();
  }, []);

  // Limpiar URL cuando se cierra el preview
  useEffect(() => {
    return () => {
      if (previewUrl) {
        window.URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

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

  const openPreview = async (pdf) => {
    setLoadingPreview(true);
    setPreviewPdf(pdf);
    
    try {
      const response = await axios.get(`${API}/pdfs/${pdf.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      setPreviewUrl(url);
    } catch (error) {
      toast.error('Error al cargar vista previa');
      setPreviewPdf(null);
    } finally {
      setLoadingPreview(false);
    }
  };

  const closePreview = () => {
    if (previewUrl) {
      window.URL.revokeObjectURL(previewUrl);
    }
    setPreviewPdf(null);
    setPreviewUrl(null);
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

  const openInNewTab = () => {
    if (previewUrl) {
      window.open(previewUrl, '_blank');
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
        <p className="text-zinc-500 mt-2">Documentos de pago consolidados listos para ver y descargar</p>
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
                  </div>

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

                  {/* Botones de acción */}
                  <div className="flex gap-2 pt-2">
                    <Button
                      onClick={() => openPreview(pdf)}
                      variant="outline"
                      className="flex-1 border-zinc-300 hover:bg-zinc-100"
                    >
                      <Eye size={18} className="mr-2" />
                      Ver PDF
                    </Button>
                    <Button
                      onClick={() => downloadPDF(pdf)}
                      className="flex-1 bg-zinc-900 hover:bg-zinc-800 text-white"
                    >
                      <Download size={18} className="mr-2" />
                      Descargar
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Modal de Vista Previa del PDF */}
      <Dialog open={!!previewPdf} onOpenChange={(open) => !open && closePreview()}>
        <DialogContent className="max-w-6xl w-[95vw] h-[90vh] p-0 overflow-hidden">
          <DialogHeader className="px-6 py-4 border-b border-zinc-200 bg-zinc-50">
            <div className="flex items-center justify-between">
              <DialogTitle className="flex items-center gap-2 text-lg">
                <FileText size={20} className="text-emerald-600" />
                {previewPdf?.filename}
              </DialogTitle>
              <div className="flex items-center gap-2">
                <Button
                  onClick={openInNewTab}
                  variant="outline"
                  size="sm"
                  className="border-zinc-300"
                >
                  <Maximize2 size={16} className="mr-2" />
                  Abrir en nueva pestaña
                </Button>
                <Button
                  onClick={() => previewPdf && downloadPDF(previewPdf)}
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  <Download size={16} className="mr-2" />
                  Descargar
                </Button>
              </div>
            </div>
          </DialogHeader>
          
          <div className="flex-1 h-full bg-zinc-100">
            {loadingPreview ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-600 mx-auto mb-4"></div>
                  <p className="text-zinc-500">Cargando PDF...</p>
                </div>
              </div>
            ) : previewUrl ? (
              <iframe
                src={previewUrl}
                className="w-full h-[calc(90vh-80px)] border-0"
                title={previewPdf?.filename}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <p className="text-zinc-500">No se pudo cargar el PDF</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

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
                  Puedes ver el PDF directamente en el navegador o descargarlo para guardarlo.
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
