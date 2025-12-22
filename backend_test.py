#!/usr/bin/env python3
"""
DocFlow Backend API Testing Suite
Tests the complete document management workflow
"""

import requests
import sys
import json
import time
from datetime import datetime
from pathlib import Path

class DocFlowAPITester:
    def __init__(self, base_url="https://invoice-matcher-5.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.uploaded_docs = []
        self.batch_id = None
        self.pdf_id = None

    def log(self, message):
        """Log with timestamp"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)
        
        # Remove Content-Type for file uploads
        if files:
            test_headers.pop('Content-Type', None)

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, data=data, headers=test_headers, timeout=60)
                else:
                    response = requests.post(url, json=data, headers=test_headers, timeout=60)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=30)

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
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@docflow.com", "password": "admin123"}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.log(f"   Logged in as: {response.get('user', {}).get('email', 'Unknown')}")
            return True
        return False

    def test_upload_documents(self):
        """Upload test documents from /tmp"""
        pdf_files = [
            'comprobante_egreso_001.pdf',
            'cuenta_por_pagar_001.pdf', 
            'factura_001.pdf',
            'soporte_pago_001.pdf'
        ]
        
        document_types = [
            'comprobante_egreso',
            'cuenta_por_pagar',
            'factura', 
            'soporte_pago'
        ]
        
        for i, (filename, doc_type) in enumerate(zip(pdf_files, document_types)):
            file_path = f"/tmp/{filename}"
            if not Path(file_path).exists():
                self.log(f"❌ File not found: {file_path}")
                continue
                
            with open(file_path, 'rb') as f:
                files = {'files': (filename, f, 'application/pdf')}
                data = {'tipo_documento': doc_type}
                
                success, response = self.run_test(
                    f"Upload {filename}",
                    "POST",
                    "documents/upload",
                    200,
                    data=data,
                    files=files
                )
                
                if success and 'documents' in response:
                    uploaded = response['documents'][0]
                    self.uploaded_docs.append(uploaded['id'])
                    self.log(f"   Uploaded: {uploaded['filename']} (ID: {uploaded['id'][:8]})")
        
        return len(self.uploaded_docs) == 4

    def test_list_documents(self):
        """List uploaded documents"""
        success, response = self.run_test(
            "List Documents",
            "GET", 
            "documents/list",
            200
        )
        
        if success and 'documents' in response:
            docs = response['documents']
            self.log(f"   Found {len(docs)} documents")
            for doc in docs[-4:]:  # Show last 4
                self.log(f"   - {doc['filename']} ({doc['status']})")
            return True
        return False

    def test_analyze_documents(self):
        """Analyze all uploaded documents"""
        success_count = 0
        
        for doc_id in self.uploaded_docs:
            success, response = self.run_test(
                f"Analyze Document {doc_id[:8]}",
                "POST",
                f"documents/{doc_id}/analyze", 
                200
            )
            
            if success:
                success_count += 1
                # Wait a bit for GPT processing
                time.sleep(2)
        
        self.log(f"   Analyzed {success_count}/{len(self.uploaded_docs)} documents")
        return success_count == len(self.uploaded_docs)

    def test_create_batch(self):
        """Create batch with processed documents"""
        success, response = self.run_test(
            "Create Batch",
            "POST",
            "batches/create",
            200,
            data=self.uploaded_docs  # Send as direct list
        )
        
        if success and 'id' in response:
            self.batch_id = response['id']
            self.log(f"   Created batch: {self.batch_id[:8]}")
            return True
        return False

    def test_list_batches(self):
        """List created batches"""
        success, response = self.run_test(
            "List Batches",
            "GET",
            "batches/list", 
            200
        )
        
        if success and 'batches' in response:
            batches = response['batches']
            self.log(f"   Found {len(batches)} batches")
            for batch in batches[-2:]:  # Show last 2
                self.log(f"   - Batch {batch['id'][:8]} ({batch['status']}) - {len(batch['documentos'])} docs")
            return True
        return False

    def test_generate_pdf(self):
        """Generate consolidated PDF"""
        if not self.batch_id:
            self.log("❌ No batch ID available")
            return False
            
        success, response = self.run_test(
            "Generate Consolidated PDF",
            "POST",
            f"batches/{self.batch_id}/generate-pdf",
            200
        )
        
        if success and 'pdf_id' in response:
            self.pdf_id = response['pdf_id']
            self.log(f"   Generated PDF: {self.pdf_id[:8]}")
            return True
        return False

    def test_list_pdfs(self):
        """List consolidated PDFs"""
        success, response = self.run_test(
            "List PDFs",
            "GET",
            "pdfs/list",
            200
        )
        
        if success and 'pdfs' in response:
            pdfs = response['pdfs']
            self.log(f"   Found {len(pdfs)} PDFs")
            for pdf in pdfs[-2:]:  # Show last 2
                size_mb = pdf['file_size'] / 1024 / 1024
                self.log(f"   - {pdf['filename']} ({size_mb:.2f} MB)")
            return True
        return False

    def test_download_pdf(self):
        """Test PDF download endpoint"""
        if not self.pdf_id:
            self.log("❌ No PDF ID available")
            return False
            
        url = f"{self.base_url}/api/pdfs/{self.pdf_id}/download"
        headers = {'Authorization': f'Bearer {self.token}'}
        
        self.tests_run += 1
        self.log("🔍 Testing PDF Download...")
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                
                if 'application/pdf' in content_type and content_length > 1000:
                    self.tests_passed += 1
                    self.log(f"✅ PDF Download - Size: {content_length/1024:.1f} KB")
                    return True
                else:
                    self.log(f"❌ PDF Download - Invalid content: {content_type}, {content_length} bytes")
            else:
                self.log(f"❌ PDF Download - Status: {response.status_code}")
            
        except Exception as e:
            self.log(f"❌ PDF Download - Error: {str(e)}")
        
        return False

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        success, response = self.run_test(
            "Dashboard Stats",
            "GET",
            "dashboard/stats",
            200
        )
        
        if success:
            stats = response
            self.log(f"   Total docs: {stats.get('total_documentos', 0)}")
            self.log(f"   Total batches: {stats.get('total_lotes', 0)}")
            self.log(f"   PDFs generated: {stats.get('pdfs_generados', 0)}")
            return True
        return False

def main():
    """Run complete DocFlow API test suite"""
    print("=" * 60)
    print("🚀 DocFlow Backend API Test Suite")
    print("=" * 60)
    
    tester = DocFlowAPITester()
    
    # Test sequence
    tests = [
        ("Login", tester.test_login),
        ("Upload Documents", tester.test_upload_documents),
        ("List Documents", tester.test_list_documents),
        ("Analyze Documents", tester.test_analyze_documents),
        ("Create Batch", tester.test_create_batch),
        ("List Batches", tester.test_list_batches),
        ("Generate PDF", tester.test_generate_pdf),
        ("List PDFs", tester.test_list_pdfs),
        ("Download PDF", tester.test_download_pdf),
        ("Dashboard Stats", tester.test_dashboard_stats)
    ]
    
    failed_tests = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
        try:
            result = test_func()
            if not result:
                failed_tests.append(test_name)
        except Exception as e:
            tester.log(f"❌ {test_name} - Exception: {str(e)}")
            failed_tests.append(test_name)
    
    # Final results
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%")
    
    if failed_tests:
        print(f"\n❌ Failed Tests: {', '.join(failed_tests)}")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0

if __name__ == "__main__":
    sys.exit(main())