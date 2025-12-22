import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { FileStack, User, Calendar } from 'lucide-react';

const Audit = () => {
  const { token, user, API } = useAuth();
  const navigate = useNavigate();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Verificar que el usuario sea admin o revisor
    if (user?.role !== 'admin' && user?.role !== 'revisor') {
      toast.error('No tienes permisos para acceder a esta sección');
      navigate('/');
      return;
    }
    fetchLogs();
  }, [user]);

  const fetchLogs = async () => {
    try {
      const response = await axios.get(`${API}/audit/logs?limit=100`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setLogs(response.data.logs);
    } catch (error) {
      toast.error('Error al cargar logs de auditoría');
    } finally {
      setLoading(false);
    }
  };

  const getActionColor = (action) => {
    const colors = {
      'CREATE_USER': 'text-blue-600 bg-blue-50 border-blue-200',
      'UPLOAD_DOCUMENTS': 'text-emerald-600 bg-emerald-50 border-emerald-200',
      'ANALYZE_DOCUMENT': 'text-amber-600 bg-amber-50 border-amber-200',
      'CREATE_BATCH': 'text-purple-600 bg-purple-50 border-purple-200',
      'GENERATE_PDF': 'text-sky-600 bg-sky-50 border-sky-200',
      'DOWNLOAD_PDF': 'text-zinc-600 bg-zinc-50 border-zinc-200',
      'TOGGLE_USER': 'text-orange-600 bg-orange-50 border-orange-200',
    };
    return colors[action] || 'text-zinc-600 bg-zinc-50 border-zinc-200';
  };

  const formatAction = (action) => {
    const labels = {
      'CREATE_USER': 'Crear Usuario',
      'UPLOAD_DOCUMENTS': 'Cargar Documentos',
      'ANALYZE_DOCUMENT': 'Analizar Documento',
      'CREATE_BATCH': 'Crear Lote',
      'GENERATE_PDF': 'Generar PDF',
      'DOWNLOAD_PDF': 'Descargar PDF',
      'TOGGLE_USER': 'Cambiar Estado Usuario',
    };
    return labels[action] || action;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-zinc-500">Cargando logs...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold text-zinc-900 tracking-tight">Auditoría</h1>
        <p className="text-zinc-500 mt-2">Registro completo de actividades del sistema</p>
      </div>

      {logs.length === 0 ? (
        <Card className="border-zinc-200">
          <CardContent className="py-12 text-center">
            <FileStack size={48} className="mx-auto text-zinc-300 mb-3" />
            <p className="text-zinc-500">No hay registros de auditoría</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {logs.map((log) => (
            <Card key={log.id} className="border-zinc-200 hover:border-zinc-300 transition-colors">
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-zinc-100 flex items-center justify-center">
                    <User size={18} className="text-zinc-600" />
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="outline" className={getActionColor(log.action)}>
                        {formatAction(log.action)}
                      </Badge>
                      <span className="text-sm text-zinc-600 font-medium">{log.user_email}</span>
                    </div>
                    
                    <p className="text-sm text-zinc-700 mb-2">{log.details}</p>
                    
                    <div className="flex items-center gap-1 text-xs text-zinc-500">
                      <Calendar size={12} />
                      <span>{new Date(log.timestamp).toLocaleString('es-ES')}</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default Audit;