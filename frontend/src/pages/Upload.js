import { useState, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { toast } from 'sonner';
import { Upload as UploadIcon, FileText, CheckCircle, AlertCircle } from 'lucide-react';

const DOCUMENT_TYPES = [
  { value: 'comprobante_egreso', label: 'Comprobante de Egreso (CE)' },
  { value: 'cuenta_por_pagar', label: 'Cuenta Por Pagar' },
  { value: 'factura', label: 'Factura' },
  { value: 'soporte_pago', label: 'Soporte de Pago' },
];

const MAX_FILES = 70;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_TOTAL_SIZE = 100 * 1024 * 1024; // 100MB

const Upload = () => {
  const { token, API } = useAuth();
  const navigate = useNavigate();
  const [selectedType, setSelectedType] = useState('comprobante_egreso');
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files);
      addFiles(newFiles);
    }
  }, [files]);

  const addFiles = (newFiles) => {
    // Validar cantidad máxima
    if (files.length + newFiles.length > MAX_FILES) {
      toast.error(`Máximo ${MAX_FILES} archivos permitidos por carga`);
      return;
    }

    // Validar tamaño individual y total
    let totalSize = files.reduce((sum, f) => sum + f.size, 0);
    const invalidFiles = [];
    const validFiles = [];

    for (const file of newFiles) {
      if (file.size > MAX_FILE_SIZE) {
        invalidFiles.push(`${file.name} (${(file.size / 1024 / 1024).toFixed(2)}MB excede 10MB)`);
      } else if (totalSize + file.size > MAX_TOTAL_SIZE) {
        toast.error('El tamaño total excede 100MB');
        break;
      } else {
        validFiles.push(file);
        totalSize += file.size;
      }
    }

    if (invalidFiles.length > 0) {
      toast.error(`Archivos muy grandes: ${invalidFiles.join(', ')}`);
    }

    if (validFiles.length > 0) {
      setFiles(prev => [...prev, ...validFiles]);
      toast.success(`${validFiles.length} archivo(s) agregado(s)`);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);
      addFiles(newFiles);
    }
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error('Selecciona al menos un archivo');
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });
      formData.append('tipo_documento', selectedType);

      const response = await axios.post(`${API}/documents/upload`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
        }
      });

      // Mostrar mensaje según resultados
      const { uploaded, duplicates, duplicate_files } = response.data;
      
      if (duplicates > 0 && uploaded > 0) {
        toast.success(`¡${uploaded} documento(s) cargado(s)!`);
        toast.warning(`${duplicates} archivo(s) duplicado(s) omitido(s): ${duplicate_files.slice(0, 3).join(', ')}${duplicates > 3 ? '...' : ''}`);
      } else if (duplicates > 0 && uploaded === 0) {
        toast.error(`Todos los archivos ya existen en esta carpeta (${duplicates} duplicados)`);
      } else {
        toast.success(`¡${uploaded} documento(s) cargado(s) exitosamente!`);
      }
      
      setFiles([]);
      setUploadProgress(0);
      
      // Navigate to documents page after 1 second if something was uploaded
      if (uploaded > 0) {
        setTimeout(() => navigate('/documents'), 1000);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al cargar documentos');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-8" data-testid="upload-page">
      <div>
        <h1 className="text-4xl md:text-5xl font-bold text-zinc-900 tracking-tight">Cargar Documentos</h1>
        <p className="text-zinc-500 mt-2 leading-relaxed">
          Sube documentos de pago para procesamiento automático
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Section */}
        <div className="space-y-6">
          <Card className="border-zinc-200">
            <CardHeader>
              <CardTitle className="text-2xl">Tipo de Documento</CardTitle>
              <CardDescription>Selecciona la categoría del documento</CardDescription>
            </CardHeader>
            <CardContent>
              <Select value={selectedType} onValueChange={setSelectedType}>
                <SelectTrigger data-testid="document-type-select" className="border-zinc-200">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DOCUMENT_TYPES.map(type => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          <Card className="border-zinc-200">
            <CardHeader>
              <CardTitle className="text-2xl">Archivos</CardTitle>
              <CardDescription>Arrastra archivos o haz clic para seleccionar</CardDescription>
            </CardHeader>
            <CardContent>
              <div
                data-testid="dropzone"
                className={`border-2 border-dashed rounded-xl p-12 text-center transition-all cursor-pointer ${
                  dragActive
                    ? 'border-zinc-400 bg-zinc-100'
                    : 'border-zinc-300 bg-zinc-50/30 hover:border-zinc-400 hover:bg-zinc-50'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => document.getElementById('fileInput').click()}
              >
                <UploadIcon size={48} className="mx-auto text-zinc-400 mb-4" strokeWidth={1.5} />
                <p className="text-zinc-700 font-medium mb-1">Arrastra archivos aquí</p>
                <p className="text-sm text-zinc-500">o haz clic para seleccionar</p>
                <p className="text-xs text-zinc-400 mt-2">PDF, JPG, PNG</p>
                <p className="text-xs text-zinc-400">Máx. 70 archivos, 10MB cada uno, 100MB total</p>
              </div>
              <input
                id="fileInput"
                type="file"
                multiple
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileChange}
                className="hidden"
                data-testid="file-input"
              />
            </CardContent>
          </Card>
        </div>

        {/* Files List */}
        <div className="space-y-6">
          <Card className="border-zinc-200">
            <CardHeader>
              <CardTitle className="text-2xl">Archivos Seleccionados ({files.length})</CardTitle>
              <CardDescription>Revisa los archivos antes de cargar</CardDescription>
            </CardHeader>
            <CardContent>
              {files.length === 0 ? (
                <div className="text-center py-12 text-zinc-400">
                  <FileText size={48} className="mx-auto mb-3 opacity-50" />
                  <p className="text-sm">No hay archivos seleccionados</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {files.map((file, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-3 bg-zinc-50 border border-zinc-200 rounded-md hover:bg-zinc-100 transition-colors"
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <FileText size={20} className="text-zinc-500 flex-shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-zinc-900 truncate">{file.name}</p>
                          <p className="text-xs text-zinc-500">
                            {(file.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeFile(index)}
                        className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                      >
                        Eliminar
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {uploading && (
                <div className="mt-4">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm text-zinc-600 font-medium">Subiendo archivos...</span>
                    <span className="text-sm font-bold text-zinc-900 tabular-nums">{uploadProgress}%</span>
                  </div>
                  <Progress value={uploadProgress} className="h-2" />
                </div>
              )}

              {files.length > 0 && !uploading && (
                <Button
                  onClick={handleUpload}
                  data-testid="upload-button"
                  className="w-full mt-6 bg-zinc-900 hover:bg-zinc-800 text-white shadow-sm"
                  size="lg"
                >
                  <UploadIcon size={20} className="mr-2" />
                  Cargar {files.length} Archivo(s)
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Info Card */}
          <Card className="border-blue-200 bg-blue-50/50">
            <CardContent className="p-6">
              <div className="flex gap-3">
                <AlertCircle size={24} className="text-blue-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-blue-900 mb-1">Importante</p>
                  <p className="text-sm text-blue-700 leading-relaxed">
                    Después de subir todos los archivos a las 4 carpetas, ve a la sección 
                    <strong> Documentos </strong> y presiona el botón <strong>"ANALIZAR"</strong> para 
                    procesar todos los documentos con IA.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Upload;