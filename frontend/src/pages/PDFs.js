import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { FileText, Download, Calendar, FolderArchive, Eye, Maximize2, Users, DollarSign, Loader2 } from 'lucide-react';

const typeLabels = {
  comprobante_egreso: 'Comprobante Egreso',
  cuenta_por_pagar: 'Cuenta Por Pagar',
  factura: 'Factura',
  soporte_pago: 'Soporte de Pago',
};

const PDFs = () => {
  const { token, API } = useAuth();
  const [pdfs, setPdfs] = useState([]);
  const [batches, setBatches] = useState({});
  const [loading, setLoading] = useState(true);
  const [previewPdf, setPreviewPdf] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [pdfDetails, setPdfDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  useEffect(() => {
    fetchPDFs();
  }, []);

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

      // Filtrar PDFs vacíos (menos de 1KB probablemente están vacíos)
      const validPdfs = pdfsResponse.data.pdfs.filter(pdf => pdf.file_size > 1000);
      setPdfs(validPdfs);
      
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

  const fetchPdfDetails = async (pdfId) => {
    setLoadingDetails(true);
    try {
      const response = await axios.get(`${API}/pdfs/${pdfId}/details`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPdfDetails(response.data);
    } catch (error) {
      toast.error('Error al cargar detalles del PDF');
    } finally {
      setLoadingDetails(false);
    }
  };

  const openPreview = async (pdf) => {
    setLoadingPreview(true);
    setPreviewPdf(pdf);
    
    // Cargar detalles del PDF
    fetchPdfDetails(pdf.id);
    
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
    setPdfDetails(null);
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
        <p className="text-zinc-500 mt-2">Documentos de pago unidos por tercero y valor</p>
      </div>

      {pdfs.length === 0 ? (
        <Card className="border-zinc-200">
          <CardContent className="py-12 text-center">
            <FileText size={48} className="mx-auto text-zinc-300 mb-3" />
            <p className="text-zinc-500 mb-2">No hay PDFs consolidados generados</p>
            <p className="text-sm text-zinc-400">
              Ve a "Lotes" y crea un lote desde las sugerencias de IA para generar PDFs unidos
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
                      <CardTitle className="text-lg flex items-center gap-2 mb-2">
                        <FileText size={20} className="text-emerald-600" />
                        <span className="truncate">{pdf.filename}</span>
                      </CardTitle>
                      <CardDescription className="flex items-center gap-2">
                        <FolderArchive size={14} />
                        {numDocs} documentos unidos
                      </CardDescription>
                    </div>
                    <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200">
                      {formatFileSize(pdf.file_size)}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-4">
                  <div className="text-sm text-zinc-600">
                    <div className="flex items-center gap-2">
                      <Calendar size={14} className="text-zinc-400" />
                      <span>{new Date(pdf.created_at).toLocaleString('es-ES', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}</span>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      onClick={() => openPreview(pdf)}
                      variant="outline"
                      className="flex-1 border-zinc-300 hover:bg-zinc-100"
                    >
                      <Eye size={18} className="mr-2" />
                      Ver Documentos Unidos
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

      {/* Modal de Vista Previa del PDF con documentos unidos */}
      <Dialog open={!!previewPdf} onOpenChange={(open) => !open && closePreview()}>
        <DialogContent className="max-w-7xl w-[95vw] h-[90vh] p-0 overflow-hidden">
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
                  Pantalla Completa
                </Button>
                <Button
                  onClick={() => previewPdf && downloadPDF(previewPdf)}
                  size="sm"
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  <Download size={16} className="mr-2" />
                  Descargar PDF
                </Button>
              </div>
            </div>
          </DialogHeader>
          
          <div className="flex h-[calc(90vh-80px)]">
            {/* Panel izquierdo: Detalles de documentos unidos */}
            <div className="w-80 border-r border-zinc-200 bg-zinc-50 overflow-y-auto p-4">
              <h3 className="font-semibold text-zinc-900 mb-4 flex items-center gap-2">
                <Users size={18} className="text-emerald-600" />
                Documentos Unidos
              </h3>
              
              {loadingDetails ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="animate-spin text-zinc-400" size={24} />
                </div>
              ) : pdfDetails ? (
                <div className="space-y-4">
                  {/* Resumen */}
                  <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                    <p className="text-xs text-emerald-600 uppercase tracking-wider font-semibold mb-2">Resumen</p>
                    <div className="space-y-1 text-sm">
                      <p className="font-medium text-emerald-800">
                        {pdfDetails.summary?.terceros?.[0] || 'Sin tercero'}
                      </p>
                      <p className="text-emerald-700 flex items-center gap-1">
                        <DollarSign size={14} />
                        ${pdfDetails.summary?.valor_total?.toLocaleString('es-CO') || 0}
                      </p>
                      <p className="text-emerald-600 text-xs">
                        {pdfDetails.summary?.total_documentos || 0} documentos
                      </p>
                    </div>
                  </div>
                  
                  {/* Lista de documentos */}
                  <div className="space-y-2">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold">
                      Orden en el PDF:
                    </p>
                    {pdfDetails.documents?.map((doc, index) => (
                      <div key={doc.id} className="p-3 bg-white rounded-lg border border-zinc-200">
                        <div className="flex items-start gap-2">
                          <span className="w-6 h-6 rounded-full bg-zinc-900 text-white text-xs flex items-center justify-center flex-shrink-0">
                            {index + 1}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-zinc-900 truncate" title={doc.filename}>
                              {doc.filename}
                            </p>
                            <p className="text-xs text-zinc-500">
                              {typeLabels[doc.tipo_documento] || doc.tipo_documento}
                            </p>
                            {doc.valor && (
                              <p className="text-xs font-medium text-emerald-600 mt-1">
                                ${doc.valor.toLocaleString('es-CO')}
                              </p>
                            )}
                            {doc.tercero && (
                              <p className="text-xs text-zinc-600 mt-1 truncate" title={doc.tercero}>
                                {doc.tercero}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-zinc-500 text-sm">No hay detalles disponibles</p>
              )}
            </div>
            
            {/* Panel derecho: Vista previa del PDF */}
            <div className="flex-1 bg-zinc-100">
              {loadingPreview ? (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Loader2 className="animate-spin h-12 w-12 text-emerald-600 mx-auto mb-4" />
                    <p className="text-zinc-500">Cargando PDF...</p>
                  </div>
                </div>
              ) : previewUrl ? (
                <iframe
                  src={previewUrl}
                  className="w-full h-full border-0"
                  title={previewPdf?.filename}
                />
              ) : (
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <FileText size={48} className="mx-auto text-zinc-300 mb-3" />
                    <p className="text-zinc-500">No se pudo cargar el PDF</p>
                    <Button
                      onClick={() => previewPdf && downloadPDF(previewPdf)}
                      className="mt-4"
                    >
                      <Download size={16} className="mr-2" />
                      Descargar en su lugar
                    </Button>
                  </div>
                </div>
              )}
            </div>
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
                  Cada PDF contiene los documentos originales unidos en este orden: 
                  <strong> Comprobante de Egreso → Cuenta Por Pagar → Soporte de Pago → Factura</strong>. 
                  Los documentos se agrupan automáticamente por tercero y valor coincidente.
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
