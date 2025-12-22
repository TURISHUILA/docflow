import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { FileText, Lock } from 'lucide-react';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      await login(email, password);
      toast.success('¡Bienvenido!');
      navigate('/');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al iniciar sesión');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Side - Image */}
      <div 
        className="hidden lg:flex lg:w-1/2 bg-cover bg-center relative"
        style={{ backgroundImage: 'url(https://images.pexels.com/photos/7233376/pexels-photo-7233376.jpeg)' }}
      >
        <div className="absolute inset-0 bg-zinc-900/40"></div>
        <div className="relative z-10 flex flex-col justify-end p-12 text-white">
          <h1 className="text-5xl font-bold tracking-tight mb-4">DocFlow</h1>
          <p className="text-xl text-zinc-200 leading-relaxed">
            Sistema inteligente de gestión documental<br />
            con análisis automático y consolidación de pagos
          </p>
        </div>
      </div>

      {/* Right Side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-md">
          <div className="mb-8 text-center lg:text-left">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-lg bg-zinc-900 mb-4">
              <FileText size={32} className="text-white" strokeWidth={1.5} />
            </div>
            <h2 className="text-3xl font-bold text-zinc-900 tracking-tight">Iniciar Sesión</h2>
            <p className="text-zinc-500 mt-2">Accede a tu cuenta para continuar</p>
          </div>

          <Card className="border-zinc-200">
            <CardHeader>
              <CardTitle className="text-xl">Credenciales</CardTitle>
              <CardDescription>Ingresa tu email y contraseña</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    data-testid="email-input"
                    placeholder="usuario@ejemplo.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="border-zinc-200 focus:ring-zinc-900"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="password">Contraseña</Label>
                  <Input
                    id="password"
                    type="password"
                    data-testid="password-input"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="border-zinc-200 focus:ring-zinc-900"
                  />
                </div>

                <Button
                  type="submit"
                  data-testid="login-button"
                  disabled={loading}
                  className="w-full bg-zinc-900 hover:bg-zinc-800 text-white shadow-sm"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <Lock size={18} className="animate-pulse" />
                      Verificando...
                    </span>
                  ) : (
                    'Iniciar Sesión'
                  )}
                </Button>
              </form>

              <div className="mt-6 p-4 bg-zinc-50 rounded-lg border border-zinc-200">
                <p className="text-xs text-zinc-600 font-medium mb-2">Usuarios de prueba:</p>
                <div className="space-y-1 text-xs text-zinc-500">
                  <p><span className="font-mono">admin@docflow.com</span> / admin123</p>
                  <p><span className="font-mono">operativo@docflow.com</span> / operativo123</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <p className="text-center text-xs text-zinc-500 mt-6">
            Sistema de gestión documental seguro y auditable
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;