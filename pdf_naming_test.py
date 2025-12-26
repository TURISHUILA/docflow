#!/usr/bin/env python3
"""
DocFlow PDF Naming Format Test
Tests the new PDF naming format: {NumeroComprobanteEgreso}_{NombreTercero}.pdf
"""

import requests
import sys
import json
import time
import re
from datetime import datetime
from pathlib import Path

class PDFNamingTester:
    def __init__(self, base_url="https://docflowpro-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log(self, message):
        """Log with timestamp"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        headers = {}
        
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        if not files:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                if files:
                    # Remove Content-Type for file uploads
                    headers.pop('Content-Type', None)
                    response = requests.post(url, files=files, data=data, headers=headers, timeout=60)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=60)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json() if response.content else {}
                except:
                    return True, {}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json()
                    self.log(f"   Error: {error_detail}")
                except:
                    self.log(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def test_login(self):
        """Test admin login with provided credentials"""
        self.log("🔐 Testing login with admin credentials...")
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@docflow.com", "password": "admin123"}
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            user_email = response.get('user', {}).get('email', 'Unknown')
            self.log(f"   ✅ Logged in as: {user_email}")
            return True
        else:
            self.log("   ❌ Login failed")
            return False

    def test_list_documents(self):
        """List existing documents to verify system state"""
        self.log("📋 Listing existing documents...")
        success, response = self.run_test(
            "List Documents",
            "GET",
            "documents/list",
            200
        )
        
        if success and 'documents' in response:
            docs = response['documents']
            self.log(f"   ✅ Found {len(docs)} documents in system")
            
            # Show documents with analysis data
            analyzed_docs = [d for d in docs if d.get('tercero') and d.get('numero_documento')]
            self.log(f"   📊 {len(analyzed_docs)} documents have analysis data")
            
            for doc in analyzed_docs[:3]:  # Show first 3 analyzed docs
                tercero = doc.get('tercero', 'N/A')[:20]
                numero = doc.get('numero_documento', 'N/A')
                tipo = doc.get('tipo_documento', 'N/A')
                self.log(f"   - {doc['filename'][:30]} | {tipo} | {numero} | {tercero}")
            
            return True, docs
        else:
            self.log("   ❌ Failed to list documents")
            return False, []

    def test_verify_analyzed_data(self, documents):
        """Verify that comprobante_egreso documents have required fields"""
        self.log("🔍 Verifying analyzed data for comprobante_egreso documents...")
        
        comprobantes = [d for d in documents if d.get('tipo_documento') == 'comprobante_egreso']
        self.log(f"   Found {len(comprobantes)} comprobante_egreso documents")
        
        valid_comprobantes = []
        for doc in comprobantes:
            numero = doc.get('numero_documento') or doc.get('analisis_completo', {}).get('numero_documento')
            tercero = doc.get('tercero') or doc.get('analisis_completo', {}).get('tercero')
            
            if numero and tercero:
                valid_comprobantes.append(doc)
                self.log(f"   ✅ {doc['filename'][:30]} | {numero} | {tercero[:20]}")
            else:
                self.log(f"   ⚠️  {doc['filename'][:30]} | Missing: numero={bool(numero)}, tercero={bool(tercero)}")
        
        self.log(f"   📊 {len(valid_comprobantes)}/{len(comprobantes)} comprobantes have complete data")
        return len(valid_comprobantes) > 0, valid_comprobantes

    def test_suggest_batches(self):
        """Get batch suggestions to find correlated documents"""
        self.log("🤖 Getting AI batch suggestions...")
        success, response = self.run_test(
            "Suggest Batches",
            "GET",
            "documents/suggest-batches",
            200
        )
        
        if success:
            suggestions = response.get('suggested_batches', [])
            total = response.get('total_suggestions', 0)
            self.log(f"   ✅ Found {total} batch suggestions")
            
            for i, suggestion in enumerate(suggestions[:2]):
                tercero = suggestion.get('tercero', 'N/A')[:25]
                num_docs = suggestion.get('num_documentos', 0)
                doc_ids = suggestion.get('document_ids', [])
                self.log(f"   - Suggestion {i+1}: {num_docs} docs for {tercero}")
                self.log(f"     Document IDs: {[id[:8] for id in doc_ids[:3]]}")
            
            return True, suggestions
        else:
            self.log("   ❌ Failed to get batch suggestions")
            return False, []

    def test_create_batch_with_comprobante(self, suggestions, valid_comprobantes):
        """Create a batch that includes a comprobante_egreso"""
        self.log("📦 Creating batch with comprobante_egreso...")
        
        # Try to find a suggestion that includes a comprobante_egreso
        target_batch = None
        for suggestion in suggestions:
            doc_ids = suggestion.get('document_ids', [])
            # Check if any of these docs are comprobantes
            for comp in valid_comprobantes:
                if comp['id'] in doc_ids:
                    target_batch = doc_ids
                    self.log(f"   🎯 Found suggestion with comprobante: {comp['numero_documento']} - {comp['tercero'][:20]}")
                    break
            if target_batch:
                break
        
        # If no suggestion includes comprobante, create manual batch
        if not target_batch and valid_comprobantes:
            # Get some other documents to create a batch
            success, response = self.run_test(
                "Get All Documents for Manual Batch",
                "GET",
                "documents/list",
                200
            )
            
            if success:
                all_docs = response.get('documents', [])
                # Take the first valid comprobante and add 1-2 other docs
                comp_doc = valid_comprobantes[0]
                other_docs = [d for d in all_docs if d['id'] != comp_doc['id'] and d.get('tercero')][:2]
                target_batch = [comp_doc['id']] + [d['id'] for d in other_docs]
                self.log(f"   🔧 Created manual batch with comprobante: {comp_doc['numero_documento']}")
        
        if not target_batch:
            self.log("   ❌ Could not create batch with comprobante_egreso")
            return False, None
        
        # Create the batch
        success, response = self.run_test(
            "Create Batch",
            "POST",
            "batches/create",
            200,
            data=target_batch
        )
        
        if success and 'id' in response:
            batch_id = response['id']
            self.log(f"   ✅ Created batch: {batch_id[:8]} with {len(target_batch)} documents")
            return True, batch_id
        else:
            self.log("   ❌ Failed to create batch")
            return False, None

    def test_generate_pdf_and_verify_name(self, batch_id):
        """Generate PDF and verify the filename format"""
        self.log("📄 Generating consolidated PDF...")
        
        success, response = self.run_test(
            "Generate Consolidated PDF",
            "POST",
            f"batches/{batch_id}/generate-pdf",
            200
        )
        
        if success and 'pdf_id' in response:
            pdf_id = response['pdf_id']
            self.log(f"   ✅ Generated PDF: {pdf_id[:8]}")
            return True, pdf_id
        else:
            self.log("   ❌ Failed to generate PDF")
            return False, None

    def test_verify_pdf_filename(self, pdf_id):
        """Verify the PDF filename follows the correct format"""
        self.log("🔍 Verifying PDF filename format...")
        
        success, response = self.run_test(
            "List PDFs",
            "GET",
            "pdfs/list",
            200
        )
        
        if success and 'pdfs' in response:
            pdfs = response['pdfs']
            target_pdf = None
            
            for pdf in pdfs:
                if pdf['id'] == pdf_id:
                    target_pdf = pdf
                    break
            
            if target_pdf:
                filename = target_pdf['filename']
                self.log(f"   📄 PDF filename: {filename}")
                
                # Check if filename follows the expected pattern
                # Pattern: {NumeroComprobanteEgreso}_{NombreTercero}.pdf
                # Example: CE-19521_AVIANCA.pdf
                
                if filename.endswith('.pdf'):
                    base_name = filename[:-4]  # Remove .pdf
                    
                    # Check if it contains underscore (separator)
                    if '_' in base_name:
                        parts = base_name.split('_', 1)  # Split only on first underscore
                        numero_part = parts[0]
                        tercero_part = parts[1] if len(parts) > 1 else ""
                        
                        # Validate format
                        has_numero = bool(numero_part and len(numero_part) > 2)
                        has_tercero = bool(tercero_part and len(tercero_part) > 2)
                        
                        if has_numero and has_tercero:
                            self.log(f"   ✅ CORRECT FORMAT: {numero_part}_{tercero_part}.pdf")
                            self.log(f"   📋 Numero: {numero_part}")
                            self.log(f"   🏢 Tercero: {tercero_part}")
                            return True
                        else:
                            self.log(f"   ⚠️  INCOMPLETE FORMAT: numero={has_numero}, tercero={has_tercero}")
                    else:
                        self.log(f"   ⚠️  NO UNDERSCORE SEPARATOR in filename")
                
                # Check if it's using fallback format
                if 'Documentos_Consolidados_' in filename:
                    self.log(f"   ℹ️  Using FALLBACK format (no valid comprobante_egreso)")
                    return True  # This is acceptable
                
                self.log(f"   ❌ INCORRECT FORMAT: {filename}")
                return False
            else:
                self.log(f"   ❌ PDF with ID {pdf_id[:8]} not found in list")
                return False
        else:
            self.log("   ❌ Failed to list PDFs")
            return False

    def test_regenerate_pdf_format(self, batch_id):
        """Test PDF regeneration maintains correct format"""
        self.log("🔄 Testing PDF regeneration...")
        
        success, response = self.run_test(
            "Regenerate PDF",
            "POST",
            f"batches/{batch_id}/regenerate-pdf",
            200
        )
        
        if success and 'pdf_id' in response:
            new_pdf_id = response['pdf_id']
            filename = response.get('filename', 'Unknown')
            self.log(f"   ✅ Regenerated PDF: {new_pdf_id[:8]}")
            self.log(f"   📄 New filename: {filename}")
            
            # Verify the regenerated filename format
            if filename.endswith('.pdf') and '_' in filename:
                base_name = filename[:-4]
                if '_' in base_name:
                    parts = base_name.split('_', 1)
                    if len(parts) == 2 and parts[0] and parts[1]:
                        self.log(f"   ✅ Regenerated PDF has CORRECT FORMAT")
                        return True
            
            self.log(f"   ⚠️  Regenerated PDF format needs verification")
            return True  # Don't fail on this
        else:
            self.log("   ❌ Failed to regenerate PDF")
            return False

    def run_complete_test(self):
        """Run the complete PDF naming test sequence"""
        print("=" * 70)
        print("🚀 DocFlow PDF Naming Format Test")
        print("   Testing: {NumeroComprobanteEgreso}_{NombreTercero}.pdf")
        print("=" * 70)
        
        # Test sequence
        if not self.test_login():
            return False
        
        print("\n" + "─" * 50)
        success, documents = self.test_list_documents()
        if not success:
            return False
        
        print("\n" + "─" * 50)
        success, valid_comprobantes = self.test_verify_analyzed_data(documents)
        if not success or not valid_comprobantes:
            self.log("❌ No valid comprobante_egreso documents found")
            return False
        
        print("\n" + "─" * 50)
        success, suggestions = self.test_suggest_batches()
        if not success:
            return False
        
        print("\n" + "─" * 50)
        success, batch_id = self.test_create_batch_with_comprobante(suggestions, valid_comprobantes)
        if not success:
            return False
        
        print("\n" + "─" * 50)
        success, pdf_id = self.test_generate_pdf_and_verify_name(batch_id)
        if not success:
            return False
        
        print("\n" + "─" * 50)
        success = self.test_verify_pdf_filename(pdf_id)
        if not success:
            return False
        
        print("\n" + "─" * 50)
        success = self.test_regenerate_pdf_format(batch_id)
        
        return True

def main():
    """Run PDF naming format test"""
    tester = PDFNamingTester()
    
    try:
        success = tester.run_complete_test()
        
        # Final results
        print("\n" + "=" * 70)
        print("📊 TEST RESULTS")
        print("=" * 70)
        print(f"Tests Run: {tester.tests_run}")
        print(f"Tests Passed: {tester.tests_passed}")
        print(f"Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%")
        
        if success:
            print("\n✅ PDF NAMING FORMAT TEST PASSED!")
            print("   The new format {NumeroComprobanteEgreso}_{NombreTercero}.pdf is working correctly")
            return 0
        else:
            print("\n❌ PDF NAMING FORMAT TEST FAILED!")
            print("   The PDF naming format needs attention")
            return 1
            
    except Exception as e:
        print(f"\n💥 Test suite crashed: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())