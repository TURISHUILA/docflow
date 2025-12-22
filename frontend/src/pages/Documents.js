import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { FileText, Search, Play } from 'lucide-react';

const statusConfig = {
  cargado: { label: 'Cargado', color: 'text-sky-600 bg-sky-50 border-sky-200' },
  en_proceso: { label: 'En Proceso', color: 'text-amber-600 bg-amber-50 border-amber-200' },
  terminado: { label: 'Terminado', color: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
  revision: { label: 'Revisión', color: 'text-rose-600 bg-rose-50 border-rose-200' },
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

  const analyzeDocument = async (docId) => {
    setAnalyzing(prev => ({ ...prev, [docId]: true }));
    try {
      await axios.post(`${API}/documents/${docId}/analyze`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Documento analizado exitosamente');
      fetchDocuments();
    } catch (error) {
      toast.error('Error al analizar documento');
    } finally {
      setAnalyzing(prev => ({ ...prev, [docId]: false }));
    }
  };

  const filteredDocs = documents;

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
          <p className="text-zinc-500 mt-2">Lista de documentos cargados</p>
        </div>

        <div className="flex items-center gap-3">
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-48 border-zinc-200">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los estados</SelectItem>
              <SelectItem value="cargado">Cargado</SelectItem>
              <SelectItem value="en_proceso">En Proceso</SelectItem>
              <SelectItem value="terminado">Terminado</SelectItem>
              <SelectItem value="revision">Revisión</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {filteredDocs.length === 0 ? (
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
                      Tercero
                    </th>
                    <th className="text-right py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                      Acciones
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDocs.map((doc) => (
                    <tr key={doc.id} className="border-b border-zinc-100 hover:bg-zinc-50/50 transition-colors">
                      <td className="py-3 px-4 text-zinc-700">
                        <div className="flex items-center gap-2">
                          <FileText size={16} className="text-zinc-400" />
                          <span className="font-medium">{doc.filename}</span>
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
                        {doc.valor ? `$${doc.valor.toLocaleString()}` : '-'}
                      </td>
                      <td className="py-3 px-4 text-zinc-600">
                        {doc.tercero || '-'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        {doc.status === 'cargado' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => analyzeDocument(doc.id)}
                            disabled={analyzing[doc.id]}
                            className="text-zinc-600 hover:text-zinc-900"
                          >
                            {analyzing[doc.id] ? (
                              <span className="flex items-center gap-1">
                                <Play size={14} className="animate-pulse" />
                                Analizando...
                              </span>
                            ) : (
                              <span className="flex items-center gap-1">
                                <Search size={14} />
                                Analizar
                              </span>
                            )}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default Documents;