import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { FileText, Search, Play, RefreshCw, Eye, CheckCircle, AlertTriangle, Loader2, Trash2, Layers, FolderOpen, Receipt, FileCheck, CreditCard } from 'lucide-react';

// Configuración de colores por tipo de documento
const folderConfig = {
  comprobante_egreso: {
    label: 'Comprobante de Egreso',
    color: 'bg-blue-500',
    lightColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    textColor: 'text-blue-700',
    icon: FileCheck,
  },
  cuenta_por_pagar: {
    label: 'Cuenta Por Pagar',
    color: 'bg-amber-500',
    lightColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    textColor: 'text-amber-700',
    icon: Receipt,
  },
  factura: {
    label: 'Factura',
    color: 'bg-emerald-500',
    lightColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    textColor: 'text-emerald-700',
    icon: FileText,
  },
  soporte_pago: {
    label: 'Soporte de Pago',
    color: 'bg-purple-500',
    lightColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    textColor: 'text-purple-700',
    icon: CreditCard,
  },
};

const statusConfig = {
  cargado: { label: 'Pendiente', color: 'text-sky-600 bg-sky-50 border-sky-200' },
  en_proceso: { label: 'Validado', color: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
  terminado: { label: 'Terminado', color: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
  dividido: { label: 'Dividido', color: 'text-purple-600 bg-purple-50 border-purple-200' },
};

const Documents = () => {
  const { token, API } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState({});
  const [processingAll, setProcessingAll] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [deleting, setDeleting] = useState({});
  const [viewingDoc, setViewingDoc] = useState(null);
  const [docUrl, setDocUrl] = useState(null);
  const [loadingDoc, setLoadingDoc] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API}/documents/list`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDocuments(response.data.documents);
    } catch (error) {
      toast.error('Error al cargar documentos');
    } finally {
      setLoading(false);
    }
  };

  const analyzeDocument = async (docId, isRevalidation = false) => {
    setAnalyzing(prev => ({ ...prev, [docId]: true }));
    try {
      const response = await axios.post(`${API}/documents/${docId}/analyze`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.data.was_split) {
        toast.success(`PDF dividido: ${response.data.documents_created} documentos extraídos de ${response.data.total_pages} páginas`);
      } else if (response.data.analysis?.error) {
        toast.error(`Error: ${response.data.analysis.error}`);
      } else {
        toast.success(isRevalidation ? 'Documento re-validado' : 'Documento validado');
      }
      fetchDocuments();
    } catch (error) {
      toast.error('Error al validar documento');
    } finally {
      setAnalyzing(prev => ({ ...prev, [docId]: false }));
    }
  };

  const deleteDocument = async (docId, filename) => {
    if (!window.confirm(`¿Eliminar "${filename}"?`)) return;
    
    setDeleting(prev => ({ ...prev, [docId]: true }));
    try {
      await axios.delete(`${API}/documents/${docId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Documento eliminado');
      fetchDocuments();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al eliminar');
    } finally {
      setDeleting(prev => ({ ...prev, [docId]: false }));
    }
  };

  const viewDocument = async (doc) => {
    setViewingDoc(doc);
    setLoadingDoc(true);
    
    try {
      const response = await axios.get(`${API}/documents/${doc.id}/view`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data], { type: doc.mime_type || 'application/pdf' }));
      setDocUrl(url);
    } catch (error) {
      toast.error('Error al cargar documento');
      setViewingDoc(null);
    } finally {
      setLoadingDoc(false);
    }
  };

  const closeDocViewer = () => {
    if (docUrl) {
      window.URL.revokeObjectURL(docUrl);
    }
    setViewingDoc(null);
    setDocUrl(null);
  };

  const processAllLoaded = async () => {
    const loadedDocs = documents.filter(doc => doc.status === 'cargado' && !doc.parent_document_id);
    
    if (loadedDocs.length === 0) {
      toast.error('No hay documentos pendientes para analizar');
      return;
    }

    setProcessingAll(true);
    toast.info(`Analizando ${loadedDocs.length} documentos con IA...`);

    let successCount = 0;
    for (const doc of loadedDocs) {
      try {
        await axios.post(`${API}/documents/${doc.id}/analyze`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
        successCount++;
      } catch (error) {
        // continuar con el siguiente
      }
    }

    setProcessingAll(false);
    toast.success(`${successCount} documentos analizados exitosamente`);
    fetchDocuments();
  };

  // Agrupar documentos por tipo
  const groupedDocs = {
    comprobante_egreso: documents.filter(d => d.tipo_documento === 'comprobante_egreso' && d.status !== 'dividido'),
    cuenta_por_pagar: documents.filter(d => d.tipo_documento === 'cuenta_por_pagar' && d.status !== 'dividido'),
    factura: documents.filter(d => d.tipo_documento === 'factura' && d.status !== 'dividido'),
    soporte_pago: documents.filter(d => d.tipo_documento === 'soporte_pago' && d.status !== 'dividido'),
  };

  const pendingCount = documents.filter(doc => doc.status === 'cargado').length;
  const totalDocs = documents.filter(d => d.status !== 'dividido').length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-zinc-400" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-4xl md:text-5xl font-bold text-zinc-900 tracking-tight">Documentos</h1>
          <p className="text-zinc-500 mt-2">{totalDocs} documentos en total</p>
        </div>

        {pendingCount > 0 && (
          <Button
            onClick={processAllLoaded}
            disabled={processingAll}
            size="lg"
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8"
          >
            {processingAll ? (
              <><Loader2 size={18} className="animate-spin mr-2" />ANALIZANDO...</>
            ) : (
              <><Search size={18} className="mr-2" />ANALIZAR ({pendingCount})</>
            )}
          </Button>
        )}
      </div>

      {/* Carpetas por tipo de documento */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {Object.entries(folderConfig).map(([tipo, config]) => {
          const docs = groupedDocs[tipo] || [];
          const Icon = config.icon;
          const pendingInFolder = docs.filter(d => d.status === 'cargado').length;
          
          return (
            <Card key={tipo} className={`${config.borderColor} border-2`}>
              <CardHeader className={`${config.lightColor} rounded-t-lg`}>
                <div className="flex items-center justify-between">
                  <CardTitle className={`text-lg flex items-center gap-3 ${config.textColor}`}>
                    <div className={`w-10 h-10 ${config.color} rounded-lg flex items-center justify-center`}>
                      <Icon size={20} className="text-white" />
                    </div>
                    {config.label}
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className={config.textColor}>
                      {docs.length} docs
                    </Badge>
                    {pendingInFolder > 0 && (
                      <Badge className="bg-amber-100 text-amber-700 border-amber-300">
                        {pendingInFolder} pendientes
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              
              <CardContent className="p-0">
                {docs.length === 0 ? (
                  <div className="p-8 text-center">
                    <FolderOpen size={32} className="mx-auto text-zinc-300 mb-2" />
                    <p className="text-zinc-400 text-sm">Sin documentos</p>
                  </div>
                ) : (
                  <div className="divide-y divide-zinc-100 max-h-80 overflow-y-auto">
                    {docs.map((doc) => (
                      <div key={doc.id} className="p-3 hover:bg-zinc-50 transition-colors">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0 flex-1">
                            <FileText size={16} className="text-zinc-400 flex-shrink-0" />
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-zinc-800 truncate" title={doc.filename}>
                                {doc.filename}
                              </p>
                              <div className="flex items-center gap-2 mt-0.5">
                                {doc.tercero && (
                                  <span className="text-xs text-zinc-500 truncate max-w-[150px]" title={doc.tercero}>
                                    {doc.tercero}
                                  </span>
                                )}
                                {doc.valor && (
                                  <span className={`text-xs font-medium ${config.textColor}`}>
                                    ${doc.valor.toLocaleString('es-CO')}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-1 flex-shrink-0">
                            <Badge variant="outline" className={`text-xs ${statusConfig[doc.status]?.color || ''}`}>
                              {statusConfig[doc.status]?.label || doc.status}
                            </Badge>
                            
                            {/* Ver documento original */}
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => viewDocument(doc)}
                              className="h-8 w-8 p-0"
                              title="Ver documento original"
                            >
                              <Eye size={14} />
                            </Button>
                            
                            {/* Validar */}
                            {doc.status === 'cargado' && (
                              <Button
                                size="sm"
                                onClick={() => analyzeDocument(doc.id)}
                                disabled={analyzing[doc.id]}
                                className="h-8 bg-emerald-600 hover:bg-emerald-700 text-white"
                              >
                                {analyzing[doc.id] ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
                              </Button>
                            )}
                            
                            {/* Re-validar */}
                            {doc.status === 'en_proceso' && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => analyzeDocument(doc.id, true)}
                                disabled={analyzing[doc.id]}
                                className="h-8 border-amber-300 text-amber-700"
                              >
                                {analyzing[doc.id] ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                              </Button>
                            )}
                            
                            {/* Eliminar */}
                            {!doc.batch_id && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => deleteDocument(doc.id, doc.filename)}
                                disabled={deleting[doc.id]}
                                className="h-8 w-8 p-0 text-rose-600 hover:bg-rose-50"
                              >
                                {deleting[doc.id] ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Modal para ver documento original */}
      <Dialog open={!!viewingDoc} onOpenChange={(open) => !open && closeDocViewer()}>
        <DialogContent className="max-w-5xl w-[90vw] h-[85vh] p-0 overflow-hidden">
          <DialogHeader className="px-6 py-4 border-b border-zinc-200 bg-zinc-50">
            <div className="flex items-center justify-between">
              <DialogTitle className="flex items-center gap-2">
                <FileText size={20} className="text-zinc-600" />
                {viewingDoc?.filename}
              </DialogTitle>
              <div className="flex items-center gap-2">
                {viewingDoc?.tercero && (
                  <Badge variant="outline">{viewingDoc.tercero}</Badge>
                )}
                {viewingDoc?.valor && (
                  <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200">
                    ${viewingDoc.valor.toLocaleString('es-CO')}
                  </Badge>
                )}
              </div>
            </div>
          </DialogHeader>
          
          <div className="flex-1 h-[calc(85vh-80px)] bg-zinc-100">
            {loadingDoc ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="animate-spin text-zinc-400" size={32} />
              </div>
            ) : docUrl ? (
              viewingDoc?.mime_type?.includes('image') ? (
                <div className="h-full flex items-center justify-center p-4">
                  <img src={docUrl} alt={viewingDoc?.filename} className="max-h-full max-w-full object-contain" />
                </div>
              ) : (
                <iframe
                  src={docUrl}
                  className="w-full h-full border-0"
                  title={viewingDoc?.filename}
                />
              )
            ) : (
              <div className="flex items-center justify-center h-full">
                <p className="text-zinc-500">No se pudo cargar el documento</p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Info */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="p-4">
          <p className="text-sm text-blue-700">
            <strong>Tip:</strong> Sube todos los archivos a las 4 carpetas desde "Cargar Documentos", luego presiona el botón 
            <strong> ANALIZAR </strong> para procesar todos los documentos pendientes con IA. El sistema detectará PDFs 
            multipágina y los dividirá automáticamente.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default Documents;
