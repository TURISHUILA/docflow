import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import { FileText, Search, RefreshCw, Eye, CheckCircle, AlertTriangle, Loader2, Trash2, FolderOpen, Receipt, FileCheck, CreditCard, ShieldCheck, Sparkles } from 'lucide-react';

// Configuración de colores por tipo de documento
const folderConfig = {
  comprobante_egreso: {
    label: 'Comprobante de Egreso',
    color: 'bg-blue-500',
    lightColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    textColor: 'text-blue-700',
    icon: FileCheck,
    order: 1,
  },
  cuenta_por_pagar: {
    label: 'Cuenta Por Pagar',
    color: 'bg-amber-500',
    lightColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    textColor: 'text-amber-700',
    icon: Receipt,
    order: 2,
  },
  factura: {
    label: 'Factura',
    color: 'bg-emerald-500',
    lightColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    textColor: 'text-emerald-700',
    icon: FileText,
    order: 3,
  },
  soporte_pago: {
    label: 'Soporte de Pago',
    color: 'bg-purple-500',
    lightColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    textColor: 'text-purple-700',
    icon: CreditCard,
    order: 4,
  },
};

// Estados con colores mejorados
const statusConfig = {
  cargado: { label: 'Pendiente', color: 'text-rose-600 bg-rose-50 border-rose-300', icon: '🔴' },
  validando: { label: 'Validando...', color: 'text-amber-600 bg-amber-50 border-amber-300', icon: '🟡' },
  validado: { label: 'Validado', color: 'text-emerald-600 bg-emerald-50 border-emerald-300', icon: '🟢' },
  en_proceso: { label: 'Analizando', color: 'text-blue-600 bg-blue-50 border-blue-300', icon: '🔵' },
  analizado: { label: 'Analizado', color: 'text-indigo-600 bg-indigo-50 border-indigo-300', icon: '🔵' },
  terminado: { label: 'En Lote', color: 'text-violet-600 bg-violet-50 border-violet-300', icon: '✅' },
  dividido: { label: 'Dividido', color: 'text-purple-600 bg-purple-50 border-purple-300', icon: '📄' },
  revision: { label: 'Revisión', color: 'text-red-600 bg-red-50 border-red-300', icon: '⚠️' },
};

const Documents = () => {
  const { token, API } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState({});
  const [validatingFolder, setValidatingFolder] = useState({});
  const [analyzingAll, setAnalyzingAll] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [deleting, setDeleting] = useState({});
  const [deletingFolder, setDeletingFolder] = useState({});
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

  // Validar un documento individual
  const validateDocument = async (docId) => {
    setValidating(prev => ({ ...prev, [docId]: true }));
    try {
      await axios.post(`${API}/documents/${docId}/validate`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Documento validado');
      fetchDocuments();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al validar documento');
    } finally {
      setValidating(prev => ({ ...prev, [docId]: false }));
    }
  };

  // Validar todos los documentos de una carpeta
  const validateFolder = async (tipoDocumento) => {
    const folderLabel = folderConfig[tipoDocumento]?.label || tipoDocumento;
    setValidatingFolder(prev => ({ ...prev, [tipoDocumento]: true }));
    
    try {
      toast.info(`Validando carpeta: ${folderLabel}...`);
      const response = await axios.post(`${API}/documents/validate-folder/${tipoDocumento}`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.data.errors > 0) {
        toast.warning(`${response.data.validated} validados, ${response.data.errors} con errores`);
      } else if (response.data.validated === 0) {
        toast.info('No hay documentos pendientes de validar en esta carpeta');
      } else {
        toast.success(`${response.data.validated} documentos validados en ${folderLabel}`);
      }
      fetchDocuments();
    } catch (error) {
      toast.error('Error al validar carpeta');
    } finally {
      setValidatingFolder(prev => ({ ...prev, [tipoDocumento]: false }));
    }
  };

  // Analizar todos los documentos validados con IA
  const analyzeAllWithAI = async () => {
    setAnalyzingAll(true);
    try {
      toast.info('Iniciando análisis con IA (procesando de 5 en 5)...');
      
      let totalAnalyzed = 0;
      let remaining = 1;
      let iterations = 0;
      const maxIterations = 50; // Máximo 250 documentos (50 * 5)
      
      // Procesar en lotes hasta que no queden más
      while (remaining > 0 && iterations < maxIterations) {
        iterations++;
        try {
          const response = await axios.post(`${API}/documents/analyze-all`, {}, {
            headers: { Authorization: `Bearer ${token}` },
            timeout: 120000 // 2 minutos de timeout
          });
          
          totalAnalyzed += response.data.analyzed || 0;
          remaining = response.data.remaining || 0;
          
          if (response.data.analyzed > 0) {
            toast.success(`Lote ${iterations}: +${response.data.analyzed} analizados (Total: ${totalAnalyzed}, Restantes: ${remaining})`, { duration: 3000 });
          }
          
          // Si no se analizó nada, salir del loop
          if (response.data.analyzed === 0) {
            break;
          }
          
          // Pequeña pausa entre lotes
          await new Promise(resolve => setTimeout(resolve, 1000));
          
        } catch (batchError) {
          console.error('Error en lote:', batchError);
          if (batchError.code === 'ECONNABORTED') {
            toast.warning('El servidor tardó mucho. Reintentando...');
            continue;
          }
          toast.error('Error al analizar. Intenta de nuevo.');
          break;
        }
      }
      
      // Actualizar lista al final
      await fetchDocuments();
      
      if (totalAnalyzed > 0) {
        toast.success(`✅ ${totalAnalyzed} documentos analizados. Ve a Lotes para ver las correlaciones.`, { duration: 5000 });
      } else {
        toast.info('No hay documentos pendientes de analizar');
      }
    } catch (error) {
      toast.error('Error al analizar documentos');
    } finally {
      setAnalyzingAll(false);
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

  // Agrupar documentos por tipo (excluir los que ya están en un lote)
  const groupedDocs = {
    comprobante_egreso: documents.filter(d => d.tipo_documento === 'comprobante_egreso' && d.status !== 'dividido' && !d.batch_id),
    cuenta_por_pagar: documents.filter(d => d.tipo_documento === 'cuenta_por_pagar' && d.status !== 'dividido' && !d.batch_id),
    factura: documents.filter(d => d.tipo_documento === 'factura' && d.status !== 'dividido' && !d.batch_id),
    soporte_pago: documents.filter(d => d.tipo_documento === 'soporte_pago' && d.status !== 'dividido' && !d.batch_id),
  };

  // Contadores
  // Contadores (solo documentos disponibles, no en lotes)
  const availableDocs = documents.filter(d => d.status !== 'dividido' && !d.batch_id);
  const pendingValidation = availableDocs.filter(doc => doc.status === 'cargado').length;
  const validatedCount = availableDocs.filter(doc => doc.status === 'validado').length;
  const analyzedCount = availableDocs.filter(doc => ['analizado', 'en_proceso'].includes(doc.status)).length;
  const inBatchCount = documents.filter(d => d.batch_id).length;
  const totalDocs = availableDocs.length;
  const allValidated = pendingValidation === 0 && validatedCount > 0;

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
          <p className="text-zinc-500 mt-2">
            {totalDocs} documentos en total
            {pendingValidation > 0 && <span className="text-rose-600 font-medium"> • {pendingValidation} pendientes de validar</span>}
            {validatedCount > 0 && <span className="text-emerald-600 font-medium"> • {validatedCount} validados</span>}
            {analyzedCount > 0 && <span className="text-indigo-600 font-medium"> • {analyzedCount} analizados</span>}
            {inBatchCount > 0 && <span className="text-violet-600 font-medium"> • {inBatchCount} en lotes</span>}
          </p>
        </div>
      </div>

      {/* Botón ANALIZAR CON IA - Solo visible cuando hay validados */}
      {validatedCount > 0 && (
        <Card className="border-2 border-indigo-300 bg-gradient-to-r from-indigo-50 to-purple-50">
          <CardContent className="p-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center flex-shrink-0">
                  <Sparkles size={24} className="text-white" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-indigo-900">Analizar con IA y Correlacionar</h3>
                  <p className="text-sm text-indigo-700 mt-1">
                    Hay {validatedCount} documentos validados listos. La IA extraerá tercero, valor, fecha y 
                    correlacionará los documentos entre las 4 carpetas.
                  </p>
                </div>
              </div>
              <Button
                onClick={analyzeAllWithAI}
                disabled={analyzingAll}
                size="lg"
                className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-10 py-6 text-lg shadow-lg hover:shadow-xl transition-all"
              >
                {analyzingAll ? (
                  <><Loader2 size={22} className="animate-spin mr-3" />ANALIZANDO...</>
                ) : (
                  <><Sparkles size={22} className="mr-3" />ANALIZAR CON IA</>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Mensaje cuando hay documentos pendientes de validar */}
      {pendingValidation > 0 && (
        <Card className="border-2 border-amber-300 bg-gradient-to-r from-amber-50 to-yellow-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <AlertTriangle size={24} className="text-amber-600" />
              <p className="text-amber-800">
                <strong>{pendingValidation} documentos</strong> pendientes de validar. 
                Usa el botón <strong>"Validar Carpeta"</strong> en cada carpeta antes de analizar con IA.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Mensaje cuando todo está analizado */}
      {analyzedCount > 0 && pendingValidation === 0 && validatedCount === 0 && (
        <Card className="border-2 border-emerald-300 bg-gradient-to-r from-emerald-50 to-green-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <CheckCircle size={24} className="text-emerald-600" />
              <p className="text-emerald-800 font-medium">
                Todos los documentos han sido analizados. Ve a <strong>Lotes</strong> para ver las sugerencias de correlación.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Carpetas por tipo de documento */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {Object.entries(folderConfig)
          .sort((a, b) => a[1].order - b[1].order)
          .map(([tipo, config]) => {
          const docs = groupedDocs[tipo] || [];
          const Icon = config.icon;
          const pendingInFolder = docs.filter(d => d.status === 'cargado').length;
          const validatedInFolder = docs.filter(d => d.status === 'validado').length;
          const analyzedInFolder = docs.filter(d => ['analizado', 'terminado'].includes(d.status)).length;
          
          return (
            <Card key={tipo} className={`${config.borderColor} border-2`}>
              <CardHeader className={`${config.lightColor} rounded-t-lg py-3`}>
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className={`text-lg flex items-center gap-3 ${config.textColor}`}>
                    <div className={`w-10 h-10 ${config.color} rounded-lg flex items-center justify-center`}>
                      <Icon size={20} className="text-white" />
                    </div>
                    {config.label}
                  </CardTitle>
                  
                  <div className="flex items-center gap-2">
                    {/* Botón VALIDAR siempre visible si hay documentos */}
                    {docs.length > 0 && (
                      <Button
                        onClick={() => validateFolder(tipo)}
                        disabled={validatingFolder[tipo] || pendingInFolder === 0}
                        size="sm"
                        className={pendingInFolder > 0 
                          ? "bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
                          : "bg-zinc-200 text-zinc-500 cursor-not-allowed"
                        }
                      >
                        {validatingFolder[tipo] ? (
                          <><Loader2 size={14} className="animate-spin mr-1" />Validando...</>
                        ) : pendingInFolder > 0 ? (
                          <><ShieldCheck size={14} className="mr-1" />VALIDAR ({pendingInFolder})</>
                        ) : (
                          <><ShieldCheck size={14} className="mr-1" />VALIDAR</>
                        )}
                      </Button>
                    )}
                    
                    {/* Badges de estado */}
                    {pendingInFolder > 0 && (
                      <Badge className="bg-rose-100 text-rose-700 border-rose-300">
                        🔴 {pendingInFolder}
                      </Badge>
                    )}
                    {validatedInFolder > 0 && (
                      <Badge className="bg-emerald-100 text-emerald-700 border-emerald-300">
                        🟢 {validatedInFolder}
                      </Badge>
                    )}
                    {analyzedInFolder > 0 && (
                      <Badge className="bg-indigo-100 text-indigo-700 border-indigo-300">
                        🔵 {analyzedInFolder}
                      </Badge>
                    )}
                    <Badge variant="outline" className={config.textColor}>
                      {docs.length} docs
                    </Badge>
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
                              {statusConfig[doc.status]?.icon} {statusConfig[doc.status]?.label || doc.status}
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
                            
                            {/* Re-validar (para documentos pendientes o con error) */}
                            {['cargado', 'revision'].includes(doc.status) && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => validateDocument(doc.id)}
                                disabled={validating[doc.id]}
                                className="h-8 border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                                title="Validar documento"
                              >
                                {validating[doc.id] ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
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

      {/* Info del flujo */}
      <Card className="border-zinc-200 bg-zinc-50">
        <CardContent className="p-4">
          <p className="text-sm text-zinc-600">
            <strong>Flujo:</strong> 1) Sube documentos → 2) <strong>Valida cada carpeta</strong> (🔴→🟢) → 
            3) <strong>Analizar con IA</strong> (🟢→🔵) → 4) Ve a <strong>Lotes</strong> para correlaciones
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default Documents;
