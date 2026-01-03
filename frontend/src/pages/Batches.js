import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import { FolderArchive, Download, Plus, FileText, Sparkles, Check, X, Loader2, Trash2, RefreshCw, Rocket } from 'lucide-react';

const statusConfig = {
  cargado: { label: 'Cargado', color: 'text-sky-600 bg-sky-50 border-sky-200' },
  en_proceso: { label: 'En Proceso', color: 'text-amber-600 bg-amber-50 border-amber-200' },
  terminado: { label: 'Terminado', color: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
  revision: { label: 'Revisión', color: 'text-rose-600 bg-rose-50 border-rose-200' },
};

const Batches = () => {
  const { token, API } = useAuth();
  const navigate = useNavigate();
  const [batches, setBatches] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [generating, setGenerating] = useState({});
  const [dialogOpen, setDialogOpen] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [creatingSuggestion, setCreatingSuggestion] = useState({});
  const [deleting, setDeleting] = useState({});
  const [reanalyzing, setReanalyzing] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [reanalyzingGroup, setReanalyzingGroup] = useState({});
  const [creatingAll, setCreatingAll] = useState(false);
  const [creatingAllProgress, setCreatingAllProgress] = useState({ current: 0, total: 0 });

  useEffect(() => {
    fetchBatches();
    fetchDocuments();
    fetchSuggestions();
  }, []);

  const fetchSuggestions = async () => {
    setLoadingSuggestions(true);
    try {
      const response = await axios.get(`${API}/documents/suggest-batches`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSuggestions(response.data.suggested_batches || []);
    } catch (error) {
      console.error('Error fetching suggestions:', error);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const deleteBatch = async (batchId) => {
    if (!window.confirm('¿Estás seguro de eliminar este lote? Se eliminará también el PDF consolidado.')) {
      return;
    }
    
    setDeleting(prev => ({ ...prev, [batchId]: true }));
    try {
      await axios.delete(`${API}/batches/${batchId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Lote eliminado exitosamente');
      fetchBatches();
      fetchDocuments();
      fetchSuggestions();
    } catch (error) {
      toast.error('Error al eliminar lote');
    } finally {
      setDeleting(prev => ({ ...prev, [batchId]: false }));
    }
  };

  const fetchBatches = async () => {
    try {
      const response = await axios.get(`${API}/batches/list`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBatches(response.data.batches);
    } catch (error) {
      toast.error('Error al cargar lotes');
    } finally {
      setLoading(false);
    }
  };

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API}/documents/list`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const allDocs = response.data.documents;
      setDocuments(allDocs.filter(doc => !doc.batch_id && doc.status === 'en_proceso'));
      // Contar documentos que necesitan procesamiento (cargado o validado)
      const needsProcessing = allDocs.filter(doc => 
        doc.status === 'cargado' || doc.status === 'validado'
      ).length;
      setPendingCount(needsProcessing);
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const reanalyzeAll = async () => {
    setReanalyzing(true);
    try {
      // Paso 1: Obtener documentos pendientes de validar y analizar
      const docsResponse = await axios.get(`${API}/documents/list`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      const allDocs = docsResponse.data.documents;
      
      // Documentos que necesitan validación
      const needsValidation = allDocs.filter(doc => doc.status === 'cargado');
      // Documentos validados que necesitan análisis
      const needsAnalysis = allDocs.filter(doc => doc.status === 'validado');
      
      // Paso 1.1: Validar documentos pendientes (por carpeta)
      if (needsValidation.length > 0) {
        toast.info(`Validando ${needsValidation.length} documentos pendientes...`);
        const folders = [...new Set(needsValidation.map(d => d.tipo_documento))];
        
        for (const folder of folders) {
          try {
            await axios.post(`${API}/documents/validate-folder/${folder}`, {}, {
              headers: { Authorization: `Bearer ${token}` }
            });
          } catch (error) {
            console.error(`Error validating folder ${folder}:`, error);
          }
        }
      }
      
      // Paso 1.2: Analizar documentos validados (en lotes pequeños)
      toast.info('Analizando documentos con IA...');
      let totalAnalyzed = 0;
      let remaining = 1;
      let iterations = 0;
      const maxIterations = 50;
      
      while (remaining > 0 && iterations < maxIterations) {
        iterations++;
        try {
          const response = await axios.post(`${API}/documents/analyze-all`, {}, {
            headers: { Authorization: `Bearer ${token}` },
            timeout: 120000
          });
          
          totalAnalyzed += response.data.analyzed || 0;
          remaining = response.data.remaining || 0;
          
          if (response.data.analyzed > 0) {
            toast.success(`+${response.data.analyzed} analizados (Total: ${totalAnalyzed}, Restantes: ${remaining})`, { duration: 2000 });
          }
          
          if (response.data.analyzed === 0) break;
          await new Promise(resolve => setTimeout(resolve, 500));
        } catch (batchError) {
          console.error('Error en lote de análisis:', batchError);
          break;
        }
      }
      
      // Paso 2: Actualizar correlaciones
      toast.info('Buscando correlaciones...');
      await fetchSuggestions();
      await fetchDocuments();
      
      if (totalAnalyzed > 0) {
        toast.success(`✅ ${totalAnalyzed} documentos analizados. Revisa las sugerencias de correlación.`, { duration: 5000 });
      } else if (needsValidation.length === 0 && needsAnalysis.length === 0) {
        toast.info('No hay documentos pendientes. Las correlaciones han sido actualizadas.');
      } else {
        toast.success('Re-análisis completado. Las sugerencias han sido actualizadas.');
      }
    } catch (error) {
      toast.error('Error durante el re-análisis');
      console.error('Reanalysis error:', error);
    } finally {
      setReanalyzing(false);
    }
  };

  const createAllBatchesAndPDFs = async () => {
    if (suggestions.length === 0) {
      toast.error('No hay sugerencias para procesar');
      return;
    }

    setCreatingAll(true);
    setCreatingAllProgress({ current: 0, total: suggestions.length });
    
    let successCount = 0;
    let errorCount = 0;
    
    toast.info(`Iniciando creación de ${suggestions.length} lotes y PDFs...`);

    for (let i = 0; i < suggestions.length; i++) {
      const suggestion = suggestions[i];
      setCreatingAllProgress({ current: i + 1, total: suggestions.length });
      
      try {
        // Crear lote y generar PDF
        await axios.post(
          `${API}/batches/create-and-generate`,
          suggestion.document_ids,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        successCount++;
      } catch (error) {
        console.error(`Error en grupo ${i + 1}:`, error);
        errorCount++;
      }
    }

    setCreatingAll(false);
    setCreatingAllProgress({ current: 0, total: 0 });
    
    // Actualizar datos
    await fetchBatches();
    await fetchSuggestions();
    
    if (errorCount === 0) {
      toast.success(`¡${successCount} lotes creados y PDFs generados exitosamente!`);
    } else {
      toast.warning(`${successCount} lotes creados, ${errorCount} con errores`);
    }
    
    // Navegar a PDFs si hubo éxitos
    if (successCount > 0) {
      setTimeout(() => navigate('/pdfs'), 1500);
    }
  };

  const createBatch = async () => {
    if (selectedDocs.length === 0) {
      toast.error('Selecciona al menos un documento');
      return;
    }

    setCreating(true);
    try {
      await axios.post(
        `${API}/batches/create`,
        selectedDocs,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('Lote creado exitosamente');
      setSelectedDocs([]);
      setDialogOpen(false);
      fetchBatches();
      fetchDocuments();
      fetchSuggestions();
    } catch (error) {
      toast.error('Error al crear lote');
    } finally {
      setCreating(false);
    }
  };

  const createBatchFromSuggestion = async (suggestion, index) => {
    setCreatingSuggestion(prev => ({ ...prev, [index]: true }));
    try {
      // Crear el lote
      const batchResponse = await axios.post(
        `${API}/batches/create`,
        suggestion.document_ids,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      // Generar el PDF automáticamente
      const batchId = batchResponse.data.id;
      await axios.post(
        `${API}/batches/${batchId}/generate-pdf`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      toast.success('Lote creado y PDF generado exitosamente');
      fetchBatches();
      fetchDocuments();
      fetchSuggestions();
    } catch (error) {
      toast.error('Error al crear lote desde sugerencia');
    } finally {
      setCreatingSuggestion(prev => ({ ...prev, [index]: false }));
    }
  };

  const dismissSuggestion = (index) => {
    setSuggestions(suggestions.filter((_, i) => i !== index));
    toast.info('Sugerencia descartada');
  };

  const reanalyzeGroup = async (suggestion, index) => {
    setReanalyzingGroup(prev => ({ ...prev, [index]: true }));
    try {
      toast.info(`Re-analizando ${suggestion.num_documentos} documentos y buscando coincidencias...`);
      
      const response = await axios.post(
        `${API}/documents/reanalyze-group`,
        suggestion.document_ids,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      const { success, new_matches } = response.data;
      
      if (new_matches && new_matches.length > 0) {
        // Mostrar los nuevos documentos encontrados
        toast.success(
          `${success} documentos re-analizados. ¡Encontrados ${new_matches.length} nuevos documentos que coinciden!`,
          { duration: 5000 }
        );
        
        // Mostrar detalles de los nuevos matches
        new_matches.forEach(match => {
          toast.info(
            `Nuevo: ${match.filename} - ${match.tercero || 'Sin tercero'} - $${match.valor?.toLocaleString('es-CO') || '0'}`,
            { duration: 4000 }
          );
        });
      } else {
        toast.success(`${success} documentos re-analizados. No se encontraron documentos adicionales.`);
      }
      
      // Actualizar sugerencias para incluir los nuevos documentos
      await fetchSuggestions();
    } catch (error) {
      toast.error('Error al re-analizar el grupo');
    } finally {
      setReanalyzingGroup(prev => ({ ...prev, [index]: false }));
    }
  };

  const generatePDF = async (batchId) => {
    setGenerating(prev => ({ ...prev, [batchId]: true }));
    try {
      await axios.post(
        `${API}/batches/${batchId}/generate-pdf`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('PDF consolidado generado');
      fetchBatches();
    } catch (error) {
      toast.error('Error al generar PDF');
    } finally {
      setGenerating(prev => ({ ...prev, [batchId]: false }));
    }
  };

  const downloadPDF = async (pdfId, filename) => {
    try {
      const response = await axios.get(`${API}/pdfs/${pdfId}/download`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('PDF descargado');
    } catch (error) {
      toast.error('Error al descargar PDF');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-zinc-500">Cargando lotes...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="batches-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-4xl md:text-5xl font-bold text-zinc-900 tracking-tight">Lotes</h1>
          <p className="text-zinc-500 mt-2">Agrupa documentos y genera PDFs consolidados</p>
        </div>

        <div className="flex gap-3">
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button data-testid="create-batch-button" className="bg-zinc-900 hover:bg-zinc-800">
                <Plus size={18} className="mr-2" />
                Nuevo Lote
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Crear Nuevo Lote</DialogTitle>
                <DialogDescription>
                  Selecciona los documentos para crear un lote de procesamiento
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 max-h-96 overflow-y-auto">
                {documents.length === 0 ? (
                  <p className="text-center py-8 text-zinc-500">No hay documentos disponibles</p>
                ) : (
                  documents.map(doc => (
                    <div key={doc.id} className="flex items-center gap-3 p-3 border border-zinc-200 rounded-md hover:bg-zinc-50">
                      <Checkbox
                        checked={selectedDocs.includes(doc.id)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedDocs([...selectedDocs, doc.id]);
                          } else {
                            setSelectedDocs(selectedDocs.filter(id => id !== doc.id));
                          }
                        }}
                      />
                      <FileText size={18} className="text-zinc-400" />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-zinc-900">{doc.filename}</p>
                        <p className="text-xs text-zinc-500">{doc.tipo_documento}</p>
                      </div>
                    </div>
                  ))
                )}
              </div>
              <Button
                onClick={createBatch}
                disabled={creating || selectedDocs.length === 0}
                className="w-full bg-zinc-900 hover:bg-zinc-800"
              >
                {creating ? 'Creando...' : `Crear Lote (${selectedDocs.length} documentos)`}
              </Button>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Botón RE-ANALIZAR prominente */}
      <Card className="border-2 border-indigo-300 bg-gradient-to-r from-indigo-50 to-purple-50">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center flex-shrink-0">
                <RefreshCw size={24} className="text-white" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-indigo-900">Re-analizar y Correlacionar</h3>
                <p className="text-sm text-indigo-700 mt-1">
                  {pendingCount > 0 
                    ? `Hay ${pendingCount} documentos pendientes de procesar. ` 
                    : ''}
                  Valida, analiza con IA y busca correlaciones automáticamente entre todas las carpetas.
                </p>
              </div>
            </div>
            <Button
              onClick={reanalyzeAll}
              disabled={reanalyzing}
              size="lg"
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-10 py-6 text-lg shadow-lg hover:shadow-xl transition-all"
            >
              {reanalyzing ? (
                <><Loader2 size={22} className="animate-spin mr-3" />RE-ANALIZANDO...</>
              ) : (
                <><RefreshCw size={22} className="mr-3" />RE-ANALIZAR</>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Sugerencias de IA */}
      {(suggestions.length > 0 || loadingSuggestions) && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="text-amber-500" size={20} />
              <h2 className="text-xl font-semibold text-zinc-900">Sugerencias de IA</h2>
              <Badge variant="outline" className="ml-2">{suggestions.length} grupos</Badge>
              {loadingSuggestions && <Loader2 className="animate-spin text-zinc-400" size={18} />}
            </div>
          </div>

          {/* Botón CREAR TODOS LOS LOTES Y PDFs */}
          {suggestions.length > 0 && (
            <Card className="border-2 border-emerald-300 bg-gradient-to-r from-emerald-50 to-green-50">
              <CardContent className="p-6">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 bg-emerald-600 rounded-xl flex items-center justify-center flex-shrink-0">
                      <Rocket size={24} className="text-white" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-emerald-900">Crear Todos los Lotes y PDFs</h3>
                      <p className="text-sm text-emerald-700 mt-1">
                        Procesa automáticamente los {suggestions.length} grupos correlacionados y genera todos los PDFs consolidados.
                      </p>
                    </div>
                  </div>
                  <Button
                    onClick={createAllBatchesAndPDFs}
                    disabled={creatingAll || suggestions.length === 0}
                    size="lg"
                    className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-10 py-6 text-lg shadow-lg hover:shadow-xl transition-all"
                  >
                    {creatingAll ? (
                      <><Loader2 size={22} className="animate-spin mr-3" />PROCESANDO...</>
                    ) : (
                      <><Rocket size={22} className="mr-3" />CREAR TODOS ({suggestions.length})</>
                    )}
                  </Button>
                </div>
                
                {/* Barra de progreso */}
                {creatingAll && (
                  <div className="mt-4 space-y-2">
                    <div className="flex justify-between text-sm text-emerald-700">
                      <span>Progreso</span>
                      <span>{creatingAllProgress.current} de {creatingAllProgress.total} lotes</span>
                    </div>
                    <Progress 
                      value={(creatingAllProgress.current / creatingAllProgress.total) * 100} 
                      className="h-3 bg-emerald-200"
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          )}
          
          {suggestions.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {suggestions.map((suggestion, index) => (
                <Card key={index} className="border-amber-200 bg-amber-50/30">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg flex items-center gap-2">
                          <Sparkles className="text-amber-500" size={18} />
                          Grupo Correlacionado
                        </CardTitle>
                        <CardDescription className="mt-1">
                          {suggestion.num_documentos} documentos encontrados
                        </CardDescription>
                      </div>
                      <Badge 
                        className={
                          suggestion.confianza === 'alta' 
                            ? 'bg-emerald-100 text-emerald-700 border-emerald-200' 
                            : 'bg-amber-100 text-amber-700 border-amber-200'
                        }
                      >
                        {suggestion.confianza === 'alta' ? 'Alta Confianza' : 'Media Confianza'}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-3 p-3 bg-white rounded-lg border border-amber-200">
                      <div>
                        <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">Tercero</p>
                        <p className="text-sm font-medium text-zinc-900 truncate">{suggestion.tercero}</p>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-1">Valor</p>
                        <p className="text-sm font-bold text-zinc-900 tabular-nums">
                          ${suggestion.valor?.toLocaleString()}
                        </p>
                      </div>
                    </div>
                    
                    <div>
                      <p className="text-xs text-zinc-500 uppercase tracking-wider font-semibold mb-2">Tipos de Documentos</p>
                      <div className="flex flex-wrap gap-1">
                        {suggestion.tipos_documentos?.map((tipo, i) => (
                          <Badge key={i} variant="outline" className="text-xs border-zinc-300 text-zinc-600">
                            {tipo === 'comprobante_egreso' ? 'Comprobante Egreso' :
                             tipo === 'cuenta_por_pagar' ? 'Cuenta Por Pagar' :
                             tipo === 'factura' ? 'Factura' :
                             tipo === 'soporte_pago' ? 'Soporte Pago' : tipo}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    
                    {/* Razón de correlación (cuando viene de Claude) */}
                    {suggestion.razon_correlacion && (
                      <div className="p-2 bg-indigo-50 rounded-lg border border-indigo-200">
                        <p className="text-xs text-indigo-600 flex items-center gap-1">
                          <Sparkles size={12} />
                          <span className="font-medium">IA:</span> {suggestion.razon_correlacion}
                        </p>
                      </div>
                    )}
                    
                    {/* Tipo de correlación */}
                    {suggestion.tipo_correlacion && (
                      <div className="flex items-center gap-2">
                        <Badge 
                          variant="outline" 
                          className={
                            suggestion.tipo_correlacion === 'valor_exacto' ? 'border-emerald-300 text-emerald-700 bg-emerald-50' :
                            suggestion.tipo_correlacion === 'mismo_nit' ? 'border-blue-300 text-blue-700 bg-blue-50' :
                            suggestion.tipo_correlacion === 'mismo_tercero' ? 'border-purple-300 text-purple-700 bg-purple-50' :
                            'border-amber-300 text-amber-700 bg-amber-50'
                          }
                        >
                          {suggestion.tipo_correlacion === 'valor_exacto' ? '💰 Valor exacto' :
                           suggestion.tipo_correlacion === 'mismo_nit' ? '🏢 Mismo NIT' :
                           suggestion.tipo_correlacion === 'mismo_tercero' ? '👥 Mismo tercero' :
                           suggestion.tipo_correlacion === 'suma_facturas' ? '➕ Suma facturas' :
                           suggestion.tipo_correlacion}
                        </Badge>
                        {suggestion.nit && (
                          <span className="text-xs text-zinc-500">NIT: {suggestion.nit}</span>
                        )}
                      </div>
                    )}
                    
                    <div className="flex gap-2 pt-2">
                      <Button
                        onClick={() => createBatchFromSuggestion(suggestion, index)}
                        disabled={creatingSuggestion[index]}
                        className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        {creatingSuggestion[index] ? (
                          <>
                            <Loader2 className="animate-spin mr-2" size={16} />
                            Creando...
                          </>
                        ) : (
                          <>
                            <Check size={16} className="mr-2" />
                            Crear Lote y PDF
                          </>
                        )}
                      </Button>
                      <Button
                        onClick={() => reanalyzeGroup(suggestion, index)}
                        disabled={reanalyzingGroup[index]}
                        variant="outline"
                        className="border-indigo-300 text-indigo-700 hover:bg-indigo-50"
                        title="Re-analizar documentos de este grupo"
                      >
                        {reanalyzingGroup[index] ? (
                          <Loader2 className="animate-spin" size={16} />
                        ) : (
                          <RefreshCw size={16} />
                        )}
                      </Button>
                      <Button
                        onClick={() => dismissSuggestion(index)}
                        variant="outline"
                        className="border-zinc-300"
                      >
                        <X size={16} />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
          
          {suggestions.length === 0 && !loadingSuggestions && (
            <Card className="border-zinc-200">
              <CardContent className="py-8 text-center">
                <Sparkles size={32} className="mx-auto text-zinc-300 mb-2" />
                <p className="text-zinc-500">No hay sugerencias de correlación disponibles</p>
                <p className="text-sm text-zinc-400 mt-1">
                  Sube y procesa más documentos para que la IA encuentre correlaciones
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {batches.length === 0 ? (
        <Card className="border-zinc-200">
          <CardContent className="py-12 text-center">
            <FolderArchive size={48} className="mx-auto text-zinc-300 mb-3" />
            <p className="text-zinc-500">No hay lotes creados</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-6">
            {batches.map(batch => (
              <Card key={batch.id} className="border-zinc-200">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-xl">Lote {batch.id.substring(0, 8)}</CardTitle>
                      <CardDescription className="mt-1">
                        {batch.documentos.length} documentos - Creado: {new Date(batch.created_at).toLocaleDateString()}
                      </CardDescription>
                    </div>
                    <Badge
                      variant="outline"
                      className={statusConfig[batch.status]?.color || ''}
                    >
                      {statusConfig[batch.status]?.label || batch.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  {!batch.pdf_generado_id ? (
                    <Button
                      onClick={() => generatePDF(batch.id)}
                      disabled={generating[batch.id]}
                      className="w-full bg-zinc-900 hover:bg-zinc-800"
                      data-testid={`generate-pdf-${batch.id}`}
                    >
                      {generating[batch.id] ? 'Generando...' : 'Generar PDF Consolidado'}
                    </Button>
                  ) : (
                    <Button
                      onClick={() => downloadPDF(batch.pdf_generado_id, `consolidado_${batch.id}.pdf`)}
                      className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
                      data-testid={`download-pdf-${batch.id}`}
                    >
                      <Download size={18} className="mr-2" />
                      Descargar PDF
                    </Button>
                  )}
                  
                  {/* Botón eliminar lote */}
                  <Button
                    onClick={() => deleteBatch(batch.id)}
                    disabled={deleting[batch.id]}
                    variant="outline"
                    className="w-full border-rose-300 text-rose-600 hover:bg-rose-50"
                  >
                    {deleting[batch.id] ? (
                      <span className="flex items-center gap-2">
                        <Loader2 size={16} className="animate-spin" />
                        Eliminando...
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        <Trash2 size={16} />
                        Eliminar Lote
                      </span>
                    )}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Botón para ver todos los PDFs */}
          <Card className="border-emerald-200 bg-emerald-50/50">
            <CardContent className="p-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="font-semibold text-emerald-900 mb-1">Ver todos los PDFs consolidados</h3>
                  <p className="text-sm text-emerald-700">
                    Accede a todos los documentos consolidados generados en una vista optimizada
                  </p>
                </div>
                <Button
                  onClick={() => navigate('/pdfs')}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white flex-shrink-0"
                >
                  <FileText size={18} className="mr-2" />
                  Ver PDFs
                </Button>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};

export default Batches;