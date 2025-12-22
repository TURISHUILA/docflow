import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Users as UsersIcon, UserPlus, ToggleLeft, ToggleRight } from 'lucide-react';

const Users = () => {
  const { token, user, API } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    nombre: '',
    password: '',
    role: 'operativo'
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    // Verificar que el usuario sea admin
    if (user?.role !== 'admin') {
      toast.error('Solo administradores pueden acceder a esta sección');
      navigate('/');
      return;
    }
    fetchUsers();
  }, [user]);

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API}/users/list`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUsers(response.data.users);
    } catch (error) {
      toast.error('Error al cargar usuarios');
    } finally {
      setLoading(false);
    }
  };

  const createUser = async (e) => {
    e.preventDefault();
    setCreating(true);

    try {
      await axios.post(`${API}/auth/register`, formData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Usuario creado exitosamente');
      setDialogOpen(false);
      setFormData({ email: '', nombre: '', password: '', role: 'operativo' });
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al crear usuario');
    } finally {
      setCreating(false);
    }
  };

  const toggleUserActive = async (userId) => {
    try {
      await axios.put(
        `${API}/users/${userId}/toggle-active`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success('Estado del usuario actualizado');
      fetchUsers();
    } catch (error) {
      toast.error('Error al actualizar usuario');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-zinc-500">Cargando usuarios...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="users-page">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-4xl md:text-5xl font-bold text-zinc-900 tracking-tight">Usuarios</h1>
          <p className="text-zinc-500 mt-2">Administra usuarios y roles del sistema</p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button data-testid="create-user-button" className="bg-zinc-900 hover:bg-zinc-800">
              <UserPlus size={18} className="mr-2" />
              Nuevo Usuario
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Crear Nuevo Usuario</DialogTitle>
              <DialogDescription>
                Completa la información del nuevo usuario
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={createUser} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="nombre">Nombre Completo</Label>
                <Input
                  id="nombre"
                  data-testid="user-name-input"
                  value={formData.nombre}
                  onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                  required
                  className="border-zinc-200"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  data-testid="user-email-input"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                  className="border-zinc-200"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Contraseña</Label>
                <Input
                  id="password"
                  type="password"
                  data-testid="user-password-input"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required
                  className="border-zinc-200"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="role">Rol</Label>
                <Select value={formData.role} onValueChange={(value) => setFormData({ ...formData, role: value })}>
                  <SelectTrigger data-testid="user-role-select" className="border-zinc-200">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Administrador</SelectItem>
                    <SelectItem value="operativo">Operativo</SelectItem>
                    <SelectItem value="revisor">Revisor/Auditor</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button
                type="submit"
                disabled={creating}
                className="w-full bg-zinc-900 hover:bg-zinc-800"
                data-testid="submit-user-button"
              >
                {creating ? 'Creando...' : 'Crear Usuario'}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="border-zinc-200">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 border-b border-zinc-200">
                <tr>
                  <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                    Nombre
                  </th>
                  <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                    Email
                  </th>
                  <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                    Rol
                  </th>
                  <th className="text-left py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                    Estado
                  </th>
                  <th className="text-right py-3 px-4 text-zinc-500 uppercase tracking-wider font-semibold text-xs">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-zinc-100 hover:bg-zinc-50/50 transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-zinc-200 flex items-center justify-center text-zinc-700 font-semibold text-xs">
                          {u.nombre.charAt(0).toUpperCase()}
                        </div>
                        <span className="font-medium text-zinc-900">{u.nombre}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-zinc-600">{u.email}</td>
                    <td className="py-3 px-4">
                      <Badge
                        variant="outline"
                        className="capitalize border-zinc-200"
                      >
                        {u.role}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">
                      <Badge
                        variant="outline"
                        className={u.is_active !== false ? 'text-emerald-600 bg-emerald-50 border-emerald-200' : 'text-zinc-500 bg-zinc-50 border-zinc-200'}
                      >
                        {u.is_active !== false ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-right">
                      {u.id !== user.id && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => toggleUserActive(u.id)}
                          className="text-zinc-600 hover:text-zinc-900"
                          data-testid={`toggle-user-${u.id}`}
                        >
                          {u.is_active !== false ? (
                            <span className="flex items-center gap-1">
                              <ToggleRight size={16} />
                              Desactivar
                            </span>
                          ) : (
                            <span className="flex items-center gap-1">
                              <ToggleLeft size={16} />
                              Activar
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
    </div>
  );
};

export default Users;