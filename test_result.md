#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Aplicación inteligente para gestionar documentos de pago con:
  - Carga de documentos (PDF, JPG, PNG)
  - Clasificación automática por tipo
  - Extracción de datos con IA (valores, fechas, terceros, conceptos)
  - Correlación inteligente para agrupar documentos relacionados
  - Generación de PDF consolidado (uniendo documentos originales)

backend:
  - task: "Login/Autenticación JWT"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Probado con curl - login funciona correctamente"

  - task: "Extracción de datos con IA (Gemini)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: false
        agent: "main"
        comment: "GPT-5.2 no soporta archivos adjuntos"
      - working: true
        agent: "main"
        comment: "Cambiado a Gemini 2.5 Flash - extracción funcionando correctamente"
      - working: true
        agent: "testing"
        comment: "Verificado - extrae valor, tercero, concepto correctamente"

  - task: "Correlación de documentos"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Endpoint /api/documents/suggest-batches implementado, necesita test con datos correlacionados"
      - working: true
        agent: "main"
        comment: "Algoritmo mejorado con matching parcial de terceros - encuentra 2 grupos correlacionados"

  - task: "UI Sugerencias de IA"
    implemented: true
    working: true
    file: "/app/frontend/src/pages/Batches.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Implementada interfaz con sugerencias de IA, botones crear lote y descartar"

  - task: "Generación de PDF consolidado"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: true
        agent: "main"
        comment: "Une documentos originales en orden especificado"

frontend:
  - task: "Lista de documentos con datos extraídos"
    implemented: true
    working: true
    file: "/app/frontend/src/pages/Documents.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Muestra valor y tercero extraídos correctamente"

  - task: "Dashboard con estadísticas"
    implemented: true
    working: true
    file: "/app/frontend/src/pages/Dashboard.js"
    stuck_count: 0
    priority: "medium"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Muestra totales y progreso de procesamiento"

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 1
  run_ui: true

test_plan:
  current_focus:
    - "Extracción de datos con IA (Gemini)"
    - "Correlación de documentos"
    - "Generación de PDF consolidado"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      NUEVO CAMBIO: Se implementó el formato de nombre para los PDFs generados.
      Formato: {NumeroComprobanteEgreso}_{NombreTercero}.pdf
      Ejemplo: CE-19521_AVIANCA.pdf
      
      Cambios realizados en /app/backend/server.py:
      1. Nueva función sanitize_filename() - sanitiza nombres para uso en archivos
      2. Nueva función generate_pdf_filename_from_batch() - genera el nombre basado en el comprobante de egreso
      3. Modificada función regenerate_pdf() - usa el nuevo nombre
      4. Modificada función generate_consolidated_pdf() - usa el nuevo nombre
      
      Necesito que pruebes:
      1. Crear un lote con documentos que incluyan un comprobante de egreso analizado
      2. Generar el PDF consolidado
      3. Verificar que el nombre del PDF tenga el formato correcto: {NumeroComprobanteEgreso}_{NombreTercero}.pdf
      4. Probar regenerar el PDF y verificar que mantenga el formato correcto
      
      Credenciales de prueba:
      - Email: admin@docflow.com
      - Password: admin123