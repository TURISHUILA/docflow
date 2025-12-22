import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileText, FolderArchive, CheckCircle, AlertCircle, Clock, Upload } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

const StatCard = ({ icon: Icon, title, value, color, testId }) => (
  <Card className="border-zinc-200" data-testid={testId}>
    <CardContent className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wider text-zinc-500 font-semibold mb-1">{title}</p>
          <p className="text-3xl font-bold text-zinc-900 tabular-nums">{value}</p>
        </div>
        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={24} strokeWidth={1.5} />
        </div>
      </div>
    </CardContent>
  </Card>
);

const Dashboard = () => {
  const { token, user, API } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/stats`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-zinc-500">Cargando estadísticas...</div>
      </div>
    );
  }

  const totalDocs = stats?.total_documentos || 0;
  const processed = (stats?.documentos_terminados || 0) + (stats?.documentos_en_proceso || 0);
  const progressPercentage = totalDocs > 0 ? Math.round((processed / totalDocs) * 100) : 0;

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      {/* Header */}
      <div>
        <h1 className="text-4xl md:text-5xl font-bold text-zinc-900 tracking-tight">Dashboard</h1>
        <p className="text-zinc-500 mt-2 leading-relaxed">
          Bienvenido, <span className="font-medium text-zinc-700">{user?.nombre}</span>
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          icon={FileText}
          title="Total Documentos"
          value={stats?.total_documentos || 0}
          color="bg-zinc-100 text-zinc-700"
          testId="stat-total-docs"
        />
        <StatCard
          icon={Upload}
          title="Cargados"
          value={stats?.documentos_cargados || 0}
          color="bg-sky-50 text-sky-600"
          testId="stat-loaded-docs"
        />
        <StatCard
          icon={Clock}
          title="En Proceso"
          value={stats?.documentos_en_proceso || 0}
          color="bg-amber-50 text-amber-600"
          testId="stat-processing-docs"
        />
        <StatCard
          icon={CheckCircle}
          title="Terminados"
          value={stats?.documentos_terminados || 0}
          color="bg-emerald-50 text-emerald-600"
          testId="stat-completed-docs"
        />
      </div>

      {/* Progress Section */}
      <Card className="border-zinc-200">
        <CardHeader>
          <CardTitle className="text-2xl">Progreso de Procesamiento</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex justify-between items-center mb-2">
              <span className="text-sm text-zinc-600 font-medium">Documentos procesados</span>
              <span className="text-2xl font-bold text-zinc-900 tabular-nums">{progressPercentage}%</span>
            </div>
            <Progress value={progressPercentage} className="h-3" />
            <p className="text-xs text-zinc-500 mt-2">
              {processed} de {totalDocs} documentos procesados o en proceso
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Additional Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="border-zinc-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-rose-50 flex items-center justify-center">
                <AlertCircle size={20} className="text-rose-600" strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-zinc-500 font-semibold">Revisión</p>
                <p className="text-2xl font-bold text-zinc-900 tabular-nums">{stats?.documentos_revision || 0}</p>
              </div>
            </div>
            <p className="text-xs text-zinc-500">Documentos que requieren revisión manual</p>
          </CardContent>
        </Card>

        <Card className="border-zinc-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-zinc-100 flex items-center justify-center">
                <FolderArchive size={20} className="text-zinc-700" strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-zinc-500 font-semibold">Lotes</p>
                <p className="text-2xl font-bold text-zinc-900 tabular-nums">{stats?.total_lotes || 0}</p>
              </div>
            </div>
            <p className="text-xs text-zinc-500">Lotes de documentos creados</p>
          </CardContent>
        </Card>

        <Card className="border-zinc-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center">
                <FileText size={20} className="text-emerald-600" strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-zinc-500 font-semibold">PDFs Generados</p>
                <p className="text-2xl font-bold text-zinc-900 tabular-nums">{stats?.pdfs_generados || 0}</p>
              </div>
            </div>
            <p className="text-xs text-zinc-500">PDFs consolidados disponibles</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;