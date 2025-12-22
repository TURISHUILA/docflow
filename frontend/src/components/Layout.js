import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { 
  FileText, 
  Upload, 
  FolderArchive, 
  Users, 
  BarChart3, 
  LogOut,
  Menu,
  X,
  FileStack
} from 'lucide-react';
import { Button } from '@/components/ui/button';

const Layout = ({ children }) => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const menuItems = [
    { icon: BarChart3, label: 'Dashboard', path: '/', roles: ['admin', 'operativo', 'revisor'] },
    { icon: Upload, label: 'Cargar Documentos', path: '/upload', roles: ['admin', 'operativo'] },
    { icon: FileText, label: 'Documentos', path: '/documents', roles: ['admin', 'operativo', 'revisor'] },
    { icon: FolderArchive, label: 'Lotes', path: '/batches', roles: ['admin', 'operativo', 'revisor'] },
    { icon: FileStack, label: 'PDFs Consolidados', path: '/pdfs', roles: ['admin', 'operativo', 'revisor'] },
    { icon: Users, label: 'Usuarios', path: '/users', roles: ['admin'] },
    { icon: FileStack, label: 'Auditoría', path: '/audit', roles: ['admin', 'revisor'] },
  ];

  const filteredItems = menuItems.filter(item => 
    item.roles.includes(user?.role)
  );

  return (
    <div className="min-h-screen bg-white">
      {/* Sidebar Desktop */}
      <aside className="fixed left-0 top-0 h-full w-64 bg-zinc-50 border-r border-zinc-200 hidden md:flex flex-col">
        <div className="p-6 border-b border-zinc-200">
          <h1 className="text-2xl font-bold text-zinc-900 tracking-tight">DocFlow</h1>
          <p className="text-xs text-zinc-500 mt-1 uppercase tracking-wider font-medium">Gestión Documental</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-1">
          {filteredItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                data-testid={`nav-${item.label.toLowerCase().replace(/ /g, '-')}`}
                className={`flex items-center gap-3 px-4 py-3 rounded-md font-medium transition-colors duration-200 ${
                  isActive
                    ? 'bg-zinc-900 text-white'
                    : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
                }`}
              >
                <Icon size={20} strokeWidth={1.5} />
                <span className="text-sm">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-zinc-200">
          <div className="flex items-center gap-3 mb-3 px-2">
            <div className="w-10 h-10 rounded-full bg-zinc-200 flex items-center justify-center text-zinc-700 font-semibold">
              {user?.nombre?.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-zinc-900 truncate">{user?.nombre}</p>
              <p className="text-xs text-zinc-500 capitalize">{user?.role}</p>
            </div>
          </div>
          <Button
            onClick={handleLogout}
            data-testid="logout-button"
            variant="ghost"
            className="w-full justify-start text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100"
          >
            <LogOut size={18} className="mr-2" />
            Cerrar Sesión
          </Button>
        </div>
      </aside>

      {/* Mobile Header */}
      <header className="md:hidden fixed top-0 left-0 right-0 bg-white border-b border-zinc-200 z-50">
        <div className="flex items-center justify-between p-4">
          <h1 className="text-xl font-bold text-zinc-900">DocFlow</h1>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            data-testid="mobile-menu-button"
          >
            {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
          </Button>
        </div>
      </header>

      {/* Mobile Sidebar */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/50" onClick={() => setSidebarOpen(false)}>
          <aside className="fixed left-0 top-0 bottom-0 w-64 bg-zinc-50 border-r border-zinc-200" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-zinc-200">
              <h1 className="text-2xl font-bold text-zinc-900">DocFlow</h1>
            </div>
            
            <nav className="p-4 space-y-1">
              {filteredItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setSidebarOpen(false)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-md font-medium transition-colors ${
                      isActive
                        ? 'bg-zinc-900 text-white'
                        : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
                    }`}
                  >
                    <Icon size={20} />
                    <span className="text-sm">{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-zinc-200 bg-zinc-50">
              <Button
                onClick={handleLogout}
                variant="ghost"
                className="w-full justify-start text-zinc-600 hover:text-zinc-900"
              >
                <LogOut size={18} className="mr-2" />
                Cerrar Sesión
              </Button>
            </div>
          </aside>
        </div>
      )}

      {/* Main Content */}
      <main className="md:ml-64 min-h-screen pt-16 md:pt-0">
        <div className="p-6 md:p-8 lg:p-12">
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;