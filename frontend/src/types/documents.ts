export interface OrganizationSummary {
  id: string
  name: string
  slug: string
  role: string
}

export interface AuthUser {
  id: string
  full_name: string
  email: string
  is_active: boolean
  organizations: OrganizationSummary[]
  [key: string]: unknown
}

export interface DocumentVersion {
  id: string
  version_number: number
  storage_path: string
  file_size: number
  file_checksum: string
  extraction_status: string
  created_at: string
}

export interface DocumentRecord {
  id: string
  organization_id: string
  created_by_user_id: string
  title: string
  original_filename: string
  content_type: string
  status: string
  created_at: string
  updated_at: string
  latest_version: DocumentVersion
}

export interface RetrievedChunk {
  chunk_id: string
  document_id: string
  document_version_id: string
  chunk_index: number
  content: string
  score: number
}

export interface SemanticSearchResponse {
  query: string
  result_count: number
  results: RetrievedChunk[]
}
