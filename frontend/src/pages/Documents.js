import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { FileText, Search, Play, RefreshCw, Eye, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';

const statusConfig = {
  cargado: { label: 'Pendiente', color: 'text-sky-600 bg-sky-50 border-sky-200', icon: FileText },
  en_proceso: { label: 'Validado', color: 'text-emerald-600 bg-emerald-50 border-emerald-200', icon: CheckCircle },
  terminado: { label: 'Terminado', color: 'text-emerald-600 bg-emerald-50 border-emerald-200', icon: CheckCircle },
  revision: { label: 'Revisar', color: 'text-rose-600 bg-rose-50 border-rose-200', icon: AlertTriangle },
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
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('all');
  const [analyzing, setAnalyzing] = useState({});
  const [processingAll, setProcessingAll] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState(null);

  useEffect(() => {
    fetchDocuments();
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
    } catch (error) {
      toast.error('Error al validar documento');
    } finally {
      setAnalyzing(prev => ({ ...prev, [docId]: false }));
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
  };

  const pendingCount = documents.filter(doc => doc.status === 'cargado').length;
  const validatedCount = documents.filter(doc => doc.status === 'en_proceso' || doc.status === 'terminado').length;

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
              data-testid="process-all-button"
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
          
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-48 border-zinc-200">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los estados</SelectItem>
              <SelectItem value="cargado">Pendientes</SelectItem>
              <SelectItem value="en_proceso">Validados</SelectItem>
              <SelectItem value="terminado">Terminados</SelectItem>
              <SelectItem value="revision">Requieren Revisión</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Mensaje informativo */}
      {pendingCount > 0 && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <AlertTriangle className="text-amber-600" size={20} />
              <div>
                <p className="font-medium text-amber-900">
                  Tienes {pendingCount} documento(s) pendiente(s) de validar
                </p>
                <p className="text-sm text-amber-700">
                  Haz clic en "Validar Documentos" para que la IA analice y extraiga la información automáticamente.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

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
                    <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                      Archivo
                    </th>
                    <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                      Tipo
                    </th>
                    <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                      Estado
                    </th>
                    <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                      Valor
                    </th>
                    <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                      Tercero / NIT
                    </th>
                    <th className="text-right py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                      Acciones
                    </th>
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
                        <Badge
                          variant="outline"
                          className={`${statusConfig[doc.status]?.color || ''}`}
                        >
                          {statusConfig[doc.status]?.label || doc.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-zinc-700 font-medium tabular-nums">
                        {doc.valor ? `$${doc.valor.toLocaleString('es-CO')}` : '-'}
                      </td>
                      <td className="py-3 px-4">
                        <div className="text-zinc-700">
                          <span className="font-medium">{doc.tercero || '-'}</span>
                          {doc.nit && (
                            <span className="text-xs text-zinc-500 block">NIT: {doc.nit}</span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {/* Ver detalles */}
                          {doc.status !== 'cargado' && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setSelectedDoc(doc)}
                              className="text-zinc-600 hover:text-zinc-900"
                            >
                              <Eye size={14} className="mr-1" />
                              Ver
                            </Button>
                          )}
                          
                          {/* Validar (para pendientes) */}
                          {doc.status === 'cargado' && (
                            <Button
                              size="sm"
                              onClick={() => analyzeDocument(doc.id)}
                              disabled={analyzing[doc.id]}
                              className="bg-emerald-600 hover:bg-emerald-700 text-white"
                            >
                              {analyzing[doc.id] ? (
                                <span className="flex items-center gap-1">
                                  <Loader2 size={14} className="animate-spin" />
                                  Validando...
                                </span>
                              ) : (
                                <span className="flex items-center gap-1">
                                  <Search size={14} />
                                  Validar
                                </span>
                              )}
                            </Button>
                          )}
                          
                          {/* Re-validar (para documentos ya procesados) */}
                          {(doc.status === 'en_proceso' || doc.status === 'revision') && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => analyzeDocument(doc.id, true)}
                              disabled={analyzing[doc.id]}
                              className="border-amber-300 text-amber-700 hover:bg-amber-50"
                            >
                              {analyzing[doc.id] ? (
                                <span className="flex items-center gap-1">
                                  <Loader2 size={14} className="animate-spin" />
                                  Re-validando...
                                </span>
                              ) : (
                                <span className="flex items-center gap-1">
                                  <RefreshCw size={14} />
                                  Re-validar
                                </span>
                              )}
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
              
              {selectedDoc.referencia_bancaria && (
                <div className="p-3 bg-zinc-50 rounded-lg">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">Referencia Bancaria</p>
                  <p className="text-sm text-zinc-700">{selectedDoc.referencia_bancaria}</p>
                </div>
              )}
              
              <div className="flex justify-end gap-2 pt-4 border-t">
                <Button
                  variant="outline"
                  onClick={() => setSelectedDoc(null)}
                >
                  Cerrar
                </Button>
                <Button
                  onClick={() => {
                    analyzeDocument(selectedDoc.id, true);
                    setSelectedDoc(null);
                  }}
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
