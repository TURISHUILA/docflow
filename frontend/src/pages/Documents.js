import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { FileText, Search, Play, RefreshCw, Eye, CheckCircle, AlertTriangle, Loader2, Trash2, Calendar, FolderOpen, Scissors, Layers } from 'lucide-react';

const statusConfig = {
  cargado: { label: 'Pendiente', color: 'text-sky-600 bg-sky-50 border-sky-200', icon: FileText },
  en_proceso: { label: 'Validado', color: 'text-emerald-600 bg-emerald-50 border-emerald-200', icon: CheckCircle },
  terminado: { label: 'Terminado', color: 'text-emerald-600 bg-emerald-50 border-emerald-200', icon: CheckCircle },
  revision: { label: 'Revisar', color: 'text-rose-600 bg-rose-50 border-rose-200', icon: AlertTriangle },
  dividido: { label: 'Dividido', color: 'text-purple-600 bg-purple-50 border-purple-200', icon: Layers },
};

const typeLabels = {
  comprobante_egreso: 'Comprobante Egreso',
  cuenta_por_pagar: 'Cuenta Por Pagar',
  factura: 'Factura',
  soporte_pago: 'Soporte de Pago',
};

const Documents = () => {
  const { token, API } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [documentsByDate, setDocumentsByDate] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');
  const [analyzing, setAnalyzing] = useState({});
  const [processingAll, setProcessingAll] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [deleting, setDeleting] = useState({});
  const [deletingDate, setDeletingDate] = useState({});
  const [activeTab, setActiveTab] = useState('list');
  const [splitting, setSplitting] = useState({});
  const [splitResult, setSplitResult] = useState(null);

  useEffect(() => {
    fetchDocuments();
    fetchDocumentsByDate();
  }, [filterStatus]);

  const fetchDocuments = async () => {
    try {
      const url = filterStatus === 'all' 
        ? `${API}/documents/list`
        : `${API}/documents/list?status=${filterStatus}`;
      
      const response = await axios.get(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDocuments(response.data.documents);
    } catch (error) {
      toast.error('Error al cargar documentos');
    } finally {
      setLoading(false);
    }
  };

  const fetchDocumentsByDate = async () => {
    try {
      const response = await axios.get(`${API}/documents/by-date`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDocumentsByDate(response.data.groups || []);
    } catch (error) {
      console.error('Error fetching by date:', error);
    }
  };

  const analyzeDocument = async (docId, isRevalidation = false) => {
    setAnalyzing(prev => ({ ...prev, [docId]: true }));
    try {
      const response = await axios.post(`${API}/documents/${docId}/analyze`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.data.analysis?.error) {
        toast.error(`Error: ${response.data.analysis.error}`);
      } else {
        toast.success(isRevalidation ? 'Documento re-validado exitosamente' : 'Documento validado exitosamente');
      }
      fetchDocuments();
      fetchDocumentsByDate();
    } catch (error) {
      toast.error('Error al validar documento');
    } finally {
      setAnalyzing(prev => ({ ...prev, [docId]: false }));
    }
  };

  const deleteDocument = async (docId, filename) => {
    if (!window.confirm(`¿Estás seguro de eliminar "${filename}"?`)) {
      return;
    }
    
    setDeleting(prev => ({ ...prev, [docId]: true }));
    try {
      await axios.delete(`${API}/documents/${docId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Documento eliminado');
      fetchDocuments();
      fetchDocumentsByDate();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al eliminar');
    } finally {
      setDeleting(prev => ({ ...prev, [docId]: false }));
    }
  };

  const deleteByDate = async (date, totalCount) => {
    if (!window.confirm(`¿Estás seguro de eliminar ${totalCount} documento(s) del ${date}?`)) {
      return;
    }
    
    setDeletingDate(prev => ({ ...prev, [date]: true }));
    try {
      const response = await axios.delete(`${API}/documents/by-date/${date}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`${response.data.deleted_count} documentos eliminados`);
      fetchDocuments();
      fetchDocumentsByDate();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al eliminar');
    } finally {
      setDeletingDate(prev => ({ ...prev, [date]: false }));
    }
  };

  const splitDocument = async (docId, filename) => {
    setSplitting(prev => ({ ...prev, [docId]: true }));
    try {
      const response = await axios.post(`${API}/documents/${docId}/split-pages`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.data.success) {
        toast.success(`PDF dividido: ${response.data.valid_documents_created} documentos extraídos de ${response.data.total_pages} páginas`);
        setSplitResult(response.data);
      } else {
        toast.info(response.data.message);
      }
      
      fetchDocuments();
      fetchDocumentsByDate();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al dividir PDF');
    } finally {
      setSplitting(prev => ({ ...prev, [docId]: false }));
    }
  };

  const processAllLoaded = async () => {
    const loadedDocs = documents.filter(doc => doc.status === 'cargado');
    
    if (loadedDocs.length === 0) {
      toast.error('No hay documentos pendientes para validar');
      return;
    }

    setProcessingAll(true);
    let successCount = 0;
    let errorCount = 0;

    toast.info(`Validando ${loadedDocs.length} documentos con IA...`, { duration: 5000 });

    for (const doc of loadedDocs) {
      try {
        await axios.post(`${API}/documents/${doc.id}/analyze`, {}, {
          headers: { Authorization: `Bearer ${token}` }
        });
        successCount++;
      } catch (error) {
        errorCount++;
      }
    }

    setProcessingAll(false);
    
    if (successCount > 0) {
      toast.success(`${successCount} documentos validados exitosamente`);
    }
    if (errorCount > 0) {
      toast.error(`${errorCount} documentos fallaron`);
    }
    
    fetchDocuments();
    fetchDocumentsByDate();
  };

  const pendingCount = documents.filter(doc => doc.status === 'cargado').length;
  const validatedCount = documents.filter(doc => doc.status === 'en_proceso' || doc.status === 'terminado').length;

  const formatDate = (dateStr) => {
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('es-ES', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-zinc-500">Cargando documentos...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="documents-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-4xl md:text-5xl font-bold text-zinc-900 tracking-tight">Documentos</h1>
          <p className="text-zinc-500 mt-2">
            {documents.length} documentos • {pendingCount} pendientes • {validatedCount} validados
          </p>
        </div>

        <div className="flex items-center gap-3">
          {pendingCount > 0 && (
            <Button
              onClick={processAllLoaded}
              disabled={processingAll}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {processingAll ? (
                <span className="flex items-center gap-2">
                  <Loader2 size={16} className="animate-spin" />
                  Validando...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Play size={16} />
                  Validar Documentos ({pendingCount})
                </span>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Tabs para cambiar entre vistas */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="list" className="flex items-center gap-2">
            <FileText size={16} />
            Lista
          </TabsTrigger>
          <TabsTrigger value="by-date" className="flex items-center gap-2">
            <Calendar size={16} />
            Por Fecha
          </TabsTrigger>
        </TabsList>

        {/* Vista de Lista */}
        <TabsContent value="list" className="space-y-4">
          <div className="flex items-center gap-3">
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-48 border-zinc-200">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los estados</SelectItem>
                <SelectItem value="cargado">Pendientes</SelectItem>
                <SelectItem value="en_proceso">Validados</SelectItem>
                <SelectItem value="terminado">Terminados</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {documents.length === 0 ? (
            <Card className="border-zinc-200">
              <CardContent className="py-12 text-center">
                <FileText size={48} className="mx-auto text-zinc-300 mb-3" />
                <p className="text-zinc-500">No hay documentos</p>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-zinc-200">
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-50 border-b border-zinc-200">
                      <tr>
                        <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">Archivo</th>
                        <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">Tipo</th>
                        <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">Estado</th>
                        <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">Valor</th>
                        <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">Tercero / NIT</th>
                        <th className="text-right py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">Acciones</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((doc) => (
                        <tr key={doc.id} className="border-b border-zinc-100 hover:bg-zinc-50/50 transition-colors">
                          <td className="py-3 px-4 text-zinc-700">
                            <div className="flex items-center gap-2">
                              <FileText size={16} className="text-zinc-400" />
                              <span className="font-medium truncate max-w-[200px]" title={doc.filename}>
                                {doc.filename}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4 text-zinc-600">
                            {typeLabels[doc.tipo_documento] || doc.tipo_documento}
                          </td>
                          <td className="py-3 px-4">
                            <Badge variant="outline" className={`${statusConfig[doc.status]?.color || ''}`}>
                              {statusConfig[doc.status]?.label || doc.status}
                            </Badge>
                          </td>
                          <td className="py-3 px-4 text-zinc-700 font-medium tabular-nums">
                            {doc.valor ? `$${doc.valor.toLocaleString('es-CO')}` : '-'}
                          </td>
                          <td className="py-3 px-4">
                            <div className="text-zinc-700">
                              <span className="font-medium">{doc.tercero || '-'}</span>
                              {doc.nit && <span className="text-xs text-zinc-500 block">NIT: {doc.nit}</span>}
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              {doc.status !== 'cargado' && (
                                <Button size="sm" variant="ghost" onClick={() => setSelectedDoc(doc)} className="text-zinc-600 hover:text-zinc-900">
                                  <Eye size={14} className="mr-1" />Ver
                                </Button>
                              )}
                              
                              {doc.status === 'cargado' && (
                                <Button size="sm" onClick={() => analyzeDocument(doc.id)} disabled={analyzing[doc.id]} className="bg-emerald-600 hover:bg-emerald-700 text-white">
                                  {analyzing[doc.id] ? <Loader2 size={14} className="animate-spin" /> : <><Search size={14} className="mr-1" />Validar</>}
                                </Button>
                              )}
                              
                              {/* Botón para dividir PDF multipágina */}
                              {doc.filename?.toLowerCase().endsWith('.pdf') && doc.status !== 'dividido' && !doc.parent_document_id && (
                                <Button 
                                  size="sm" 
                                  variant="outline" 
                                  onClick={() => splitDocument(doc.id, doc.filename)} 
                                  disabled={splitting[doc.id]} 
                                  className="border-purple-300 text-purple-700 hover:bg-purple-50"
                                  title="Dividir PDF multipágina y extraer documentos"
                                >
                                  {splitting[doc.id] ? <Loader2 size={14} className="animate-spin" /> : <><Scissors size={14} className="mr-1" />Dividir</>}
                                </Button>
                              )}
                              
                              {(doc.status === 'en_proceso' || doc.status === 'revision') && (
                                <Button size="sm" variant="outline" onClick={() => analyzeDocument(doc.id, true)} disabled={analyzing[doc.id]} className="border-amber-300 text-amber-700 hover:bg-amber-50">
                                  {analyzing[doc.id] ? <Loader2 size={14} className="animate-spin" /> : <><RefreshCw size={14} className="mr-1" />Re-validar</>}
                                </Button>
                              )}
                              
                              {!doc.batch_id && doc.status !== 'dividido' && (
                                <Button size="sm" variant="ghost" onClick={() => deleteDocument(doc.id, doc.filename)} disabled={deleting[doc.id]} className="text-rose-600 hover:text-rose-700 hover:bg-rose-50">
                                  {deleting[doc.id] ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Vista por Fecha */}
        <TabsContent value="by-date" className="space-y-4">
          {documentsByDate.length === 0 ? (
            <Card className="border-zinc-200">
              <CardContent className="py-12 text-center">
                <Calendar size={48} className="mx-auto text-zinc-300 mb-3" />
                <p className="text-zinc-500">No hay documentos organizados por fecha</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {documentsByDate.map((group) => (
                <Card key={group.date} className="border-zinc-200">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center">
                          <Calendar size={20} className="text-zinc-600" />
                        </div>
                        <div>
                          <CardTitle className="text-lg capitalize">{formatDate(group.date)}</CardTitle>
                          <p className="text-sm text-zinc-500">{group.total_count} documento(s)</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {group.has_batched && (
                          <Badge variant="outline" className="text-amber-600 border-amber-300 bg-amber-50">
                            Tiene documentos en lotes
                          </Badge>
                        )}
                        {!group.has_batched && (
                          <Button
                            onClick={() => deleteByDate(group.date, group.total_count)}
                            disabled={deletingDate[group.date]}
                            variant="outline"
                            className="border-rose-300 text-rose-600 hover:bg-rose-50"
                          >
                            {deletingDate[group.date] ? (
                              <span className="flex items-center gap-2">
                                <Loader2 size={16} className="animate-spin" />
                                Eliminando...
                              </span>
                            ) : (
                              <span className="flex items-center gap-2">
                                <Trash2 size={16} />
                                Eliminar Carpeta ({group.total_count})
                              </span>
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                      {group.documents.slice(0, 6).map((doc) => (
                        <div key={doc.id} className="flex items-center gap-2 p-2 bg-zinc-50 rounded-lg">
                          <FileText size={14} className="text-zinc-400 flex-shrink-0" />
                          <span className="text-sm text-zinc-700 truncate" title={doc.filename}>
                            {doc.filename}
                          </span>
                          {doc.batch_id && (
                            <Badge variant="outline" className="text-xs ml-auto flex-shrink-0">En lote</Badge>
                          )}
                        </div>
                      ))}
                      {group.documents.length > 6 && (
                        <div className="flex items-center justify-center p-2 bg-zinc-100 rounded-lg">
                          <span className="text-sm text-zinc-500">+{group.documents.length - 6} más</span>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Modal de detalles del documento */}
      <Dialog open={!!selectedDoc} onOpenChange={(open) => !open && setSelectedDoc(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText size={20} className="text-emerald-600" />
              Detalles del Documento
            </DialogTitle>
          </DialogHeader>
          
          {selectedDoc && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-zinc-50 rounded-lg">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">Archivo</p>
                  <p className="text-sm font-medium text-zinc-900">{selectedDoc.filename}</p>
                </div>
                <div className="p-3 bg-zinc-50 rounded-lg">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">Tipo</p>
                  <p className="text-sm font-medium text-zinc-900">
                    {typeLabels[selectedDoc.tipo_documento] || selectedDoc.tipo_documento}
                  </p>
                </div>
                <div className="p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                  <p className="text-xs text-emerald-600 uppercase tracking-wider font-semibold mb-1">Valor</p>
                  <p className="text-lg font-bold text-emerald-700">
                    {selectedDoc.valor ? `$${selectedDoc.valor.toLocaleString('es-CO')}` : 'No detectado'}
                  </p>
                </div>
                <div className="p-3 bg-zinc-50 rounded-lg">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">Fecha</p>
                  <p className="text-sm font-medium text-zinc-900">{selectedDoc.fecha || 'No detectada'}</p>
                </div>
              </div>
              
              <div className="p-3 bg-zinc-50 rounded-lg">
                <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">Tercero / Beneficiario</p>
                <p className="text-sm font-medium text-zinc-900">{selectedDoc.tercero || 'No detectado'}</p>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-zinc-50 rounded-lg">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">NIT</p>
                  <p className="text-sm font-medium text-zinc-900">{selectedDoc.nit || 'No detectado'}</p>
                </div>
                <div className="p-3 bg-zinc-50 rounded-lg">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">Número Documento</p>
                  <p className="text-sm font-medium text-zinc-900">{selectedDoc.numero_documento || 'No detectado'}</p>
                </div>
              </div>
              
              <div className="p-3 bg-zinc-50 rounded-lg">
                <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">Concepto</p>
                <p className="text-sm text-zinc-700">{selectedDoc.concepto || 'No detectado'}</p>
              </div>
              
              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button variant="outline" onClick={() => setSelectedDoc(null)}>Cerrar</Button>
                <Button
                  onClick={() => { analyzeDocument(selectedDoc.id, true); setSelectedDoc(null); }}
                  disabled={analyzing[selectedDoc.id]}
                  className="bg-amber-600 hover:bg-amber-700 text-white"
                >
                  <RefreshCw size={16} className="mr-2" />
                  Volver a Validar
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Documents;
