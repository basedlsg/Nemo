import { useState, useEffect } from "react";
import Head from "next/head";

interface QueryResponse {
  answer_zh: string;
  citations: Array<{
    citation_id: string;
    title: string;
    effective_date: string;
    url?: string;
  }>;
  sections: number;
  total_citations: number;
  processing_time_ms: number;
  trace_id: string;
}

interface ErrorResponse {
  error: string;
  refusal_code?: string;
  message: string;
  message_en?: string;
  suggestion: string;
  suggestion_en?: string;
  policy_violated?: string;
  trace_id: string;
  can_request_ingestion?: boolean;
  ingestion_request_url?: string;
  error_category?: string;
  severity?: string;
}

interface IngestionRequest {
  query: string;
  province: string;
  asset_type: string;
  doc_class: string;
  refusal_code: string;
  user_email?: string;
  justification: string;
  priority: 'low' | 'medium' | 'high';
}

// Ingestion Request Modal Component
function IngestionRequestModal({
  request,
  lang,
  onSubmit,
  onClose,
  onUpdate
}: {
  request: IngestionRequest;
  lang: string;
  onSubmit: (request: IngestionRequest) => void;
  onClose: () => void;
  onUpdate: (request: IngestionRequest) => void;
}) {
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!request.justification.trim()) {
      alert(lang === 'zh-CN' ? '请填写申请理由' : 'Please provide justification');
      return;
    }
    
    setSubmitting(true);
    try {
      await onSubmit(request);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '1rem'
    }}>
      <div style={{
        background: 'white',
        borderRadius: '0.75rem',
        padding: '2rem',
        maxWidth: '500px',
        width: '100%',
        maxHeight: '90vh',
        overflowY: 'auto',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1.5rem'
        }}>
          <h3 style={{
            fontSize: '1.25rem',
            fontWeight: 700,
            color: '#2d3748',
            margin: 0
          }}>
            📝 {lang === 'zh-CN' ? '申请补充资料' : 'Request Data Ingestion'}
          </h3>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.5rem',
              cursor: 'pointer',
              color: '#718096',
              padding: '0.25rem'
            }}
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Request Summary */}
          <div style={{
            background: '#f7fafc',
            padding: '1rem',
            borderRadius: '0.5rem',
            marginBottom: '1.5rem',
            border: '1px solid #e2e8f0'
          }}>
            <div style={{ fontSize: '0.875rem', color: '#4a5568', marginBottom: '0.5rem' }}>
              <strong>{lang === 'zh-CN' ? '查询信息' : 'Query Information'}</strong>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#718096', lineHeight: '1.5' }}>
              <div><strong>{lang === 'zh-CN' ? '问题' : 'Question'}:</strong> {request.query}</div>
              <div><strong>{lang === 'zh-CN' ? '省份' : 'Province'}:</strong> {request.province}</div>
              <div><strong>{lang === 'zh-CN' ? '资产类型' : 'Asset Type'}:</strong> {request.asset_type}</div>
              <div><strong>{lang === 'zh-CN' ? '文档类别' : 'Document Class'}:</strong> {request.doc_class}</div>
              <div><strong>{lang === 'zh-CN' ? '拒绝代码' : 'Refusal Code'}:</strong> {request.refusal_code}</div>
            </div>
          </div>

          {/* Email Input */}
          <div style={{ marginBottom: '1rem' }}>
            <label style={{
              display: 'block',
              fontSize: '0.875rem',
              fontWeight: 500,
              color: '#374151',
              marginBottom: '0.5rem'
            }}>
              {lang === 'zh-CN' ? '联系邮箱（可选）' : 'Contact Email (Optional)'}
            </label>
            <input
              type="email"
              value={request.user_email || ''}
              onChange={(e) => onUpdate({ ...request, user_email: e.target.value })}
              placeholder={lang === 'zh-CN' ? '您的邮箱地址' : 'Your email address'}
              style={{
                width: '100%',
                padding: '0.75rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                fontSize: '0.875rem'
              }}
            />
          </div>

          {/* Priority Selection */}
          <div style={{ marginBottom: '1rem' }}>
            <label style={{
              display: 'block',
              fontSize: '0.875rem',
              fontWeight: 500,
              color: '#374151',
              marginBottom: '0.5rem'
            }}>
              {lang === 'zh-CN' ? '优先级' : 'Priority'}
            </label>
            <select
              value={request.priority}
              onChange={(e) => onUpdate({ ...request, priority: e.target.value as 'low' | 'medium' | 'high' })}
              style={{
                width: '100%',
                padding: '0.75rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                fontSize: '0.875rem'
              }}
            >
              <option value="low">{lang === 'zh-CN' ? '低 - 一般需求' : 'Low - General Need'}</option>
              <option value="medium">{lang === 'zh-CN' ? '中 - 业务需要' : 'Medium - Business Need'}</option>
              <option value="high">{lang === 'zh-CN' ? '高 - 紧急需求' : 'High - Urgent Need'}</option>
            </select>
          </div>

          {/* Justification */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{
              display: 'block',
              fontSize: '0.875rem',
              fontWeight: 500,
              color: '#374151',
              marginBottom: '0.5rem'
            }}>
              {lang === 'zh-CN' ? '申请理由 *' : 'Justification *'}
            </label>
            <textarea
              value={request.justification}
              onChange={(e) => onUpdate({ ...request, justification: e.target.value })}
              placeholder={lang === 'zh-CN' 
                ? '请详细说明为什么需要这些资料，以及如何使用这些信息...' 
                : 'Please explain why you need this information and how you plan to use it...'}
              rows={4}
              style={{
                width: '100%',
                padding: '0.75rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
                resize: 'vertical',
                fontFamily: 'inherit'
              }}
              required
            />
          </div>

          {/* Action Buttons */}
          <div style={{
            display: 'flex',
            gap: '0.75rem',
            justifyContent: 'flex-end'
          }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '0.75rem 1.5rem',
                border: '1px solid #d1d5db',
                borderRadius: '0.375rem',
                background: 'white',
                color: '#374151',
                fontSize: '0.875rem',
                fontWeight: 500,
                cursor: 'pointer'
              }}
            >
              {lang === 'zh-CN' ? '取消' : 'Cancel'}
            </button>
            <button
              type="submit"
              disabled={submitting || !request.justification.trim()}
              style={{
                padding: '0.75rem 1.5rem',
                border: 'none',
                borderRadius: '0.375rem',
                background: submitting || !request.justification.trim() ? '#9ca3af' : '#3b82f6',
                color: 'white',
                fontSize: '0.875rem',
                fontWeight: 500,
                cursor: submitting || !request.justification.trim() ? 'not-allowed' : 'pointer'
              }}
            >
              {submitting 
                ? (lang === 'zh-CN' ? '提交中...' : 'Submitting...') 
                : (lang === 'zh-CN' ? '提交申请' : 'Submit Request')
              }
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Refusal Display Component
function RefusalDisplay({ 
  error, 
  lang, 
  onRequestIngestion 
}: { 
  error: ErrorResponse; 
  lang: string; 
  onRequestIngestion: (error: ErrorResponse) => void;
}) {
  const getRefusalIcon = (code?: string) => {
    switch (code) {
      case 'no_first_party_citation':
      case 'stale_citation':
      case 'insufficient_citations':
        return '📚';
      case 'province_mismatch':
      case 'cross_province_leakage':
        return '🗺️';
      case 'language_policy_violation':
        return '🌐';
      case 'unsafe_content':
      case 'prompt_injection':
        return '🛡️';
      case 'system_overload':
      case 'retrieval_failed':
        return '⚠️';
      default:
        return '❌';
    }
  };

  const getRefusalSeverity = (code?: string) => {
    const highSeverity = ['unsafe_content', 'prompt_injection', 'cross_province_leakage'];
    const mediumSeverity = ['province_mismatch', 'language_policy_violation', 'stale_citation'];
    
    if (highSeverity.includes(code || '')) return 'high';
    if (mediumSeverity.includes(code || '')) return 'medium';
    return 'low';
  };

  const severity = getRefusalSeverity(error.refusal_code);
  const severityColors = {
    high: { bg: '#fed7d7', border: '#feb2b2', text: '#c53030' },
    medium: { bg: '#fef5e7', border: '#f6e05e', text: '#d69e2e' },
    low: { bg: '#e6fffa', border: '#81e6d9', text: '#319795' }
  };
  const colors = severityColors[severity];

  return (
    <div style={{
      background: colors.bg,
      border: `1px solid ${colors.border}`,
      padding: '1.5rem',
      borderRadius: '0.75rem',
      marginBottom: '2rem',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
    }}>
      {/* Refusal Header */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '1rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <span style={{ fontSize: '1.5rem', marginRight: '0.5rem' }}>
            {getRefusalIcon(error.refusal_code)}
          </span>
          <span style={{ 
            fontSize: '1.25rem', 
            fontWeight: 700, 
            color: colors.text
          }}>
            {lang === 'zh-CN' ? '查询被拒绝' : 'Query Refused'}
          </span>
        </div>
        
        {error.refusal_code && (
          <div style={{
            background: 'rgba(255, 255, 255, 0.8)',
            padding: '0.25rem 0.75rem',
            borderRadius: '1rem',
            fontSize: '0.75rem',
            fontWeight: 500,
            color: colors.text,
            border: `1px solid ${colors.border}`
          }}>
            {error.refusal_code.toUpperCase()}
          </div>
        )}
      </div>

      {/* Refusal Message */}
      <div style={{ 
        color: colors.text, 
        marginBottom: '1rem',
        fontSize: '1rem',
        lineHeight: '1.6'
      }}>
        {error.message}
      </div>
      
      {/* Suggestion */}
      <div style={{ 
        background: 'rgba(255, 255, 255, 0.6)',
        padding: '0.75rem',
        borderRadius: '0.5rem',
        marginBottom: '1rem',
        border: `1px solid ${colors.border}`
      }}>
        <div style={{ 
          fontSize: '0.875rem',
          fontWeight: 600,
          color: colors.text,
          marginBottom: '0.25rem'
        }}>
          {lang === 'zh-CN' ? '💡 建议' : '💡 Suggestion'}
        </div>
        <div style={{ 
          fontSize: '0.875rem',
          color: colors.text,
          lineHeight: '1.5'
        }}>
          {error.suggestion}
        </div>
      </div>

      {/* Policy Information */}
      {error.policy_violated && (
        <div style={{ 
          background: 'rgba(255, 255, 255, 0.4)',
          padding: '0.75rem',
          borderRadius: '0.5rem',
          marginBottom: '1rem',
          border: `1px dashed ${colors.border}`
        }}>
          <div style={{ 
            fontSize: '0.75rem',
            fontWeight: 600,
            color: colors.text,
            marginBottom: '0.25rem'
          }}>
            {lang === 'zh-CN' ? '违反政策' : 'Policy Violated'}
          </div>
          <div style={{ 
            fontSize: '0.75rem',
            color: colors.text
          }}>
            {error.policy_violated}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div style={{ 
        display: 'flex', 
        gap: '0.75rem',
        flexWrap: 'wrap',
        alignItems: 'center'
      }}>
        {/* Request Ingestion Button */}
        {error.can_request_ingestion && (
          <button
            onClick={() => onRequestIngestion(error)}
            style={{
              background: colors.text,
              color: 'white',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '0.375rem',
              fontSize: '0.875rem',
              fontWeight: 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              transition: 'all 0.2s'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.opacity = '0.9';
              e.currentTarget.style.transform = 'translateY(-1px)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.opacity = '1';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            📝 {lang === 'zh-CN' ? '请求补充资料' : 'Request Data Ingestion'}
          </button>
        )}

        {/* Help Button */}
        <button
          onClick={() => window.open('/help/refusal-codes', '_blank')}
          style={{
            background: 'transparent',
            color: colors.text,
            border: `1px solid ${colors.text}`,
            padding: '0.5rem 1rem',
            borderRadius: '0.375rem',
            fontSize: '0.875rem',
            fontWeight: 500,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem'
          }}
        >
          ❓ {lang === 'zh-CN' ? '了解更多' : 'Learn More'}
        </button>
      </div>

      {/* Trace ID */}
      <div style={{ 
        fontSize: '0.75rem', 
        color: colors.text,
        opacity: 0.7,
        marginTop: '1rem',
        textAlign: 'right'
      }}>
        Trace ID: {error.trace_id}
      </div>
    </div>
  );
}

export default function Home() {
  const [province, setProvince] = useState("guangdong");
  const [docClass, setDocClass] = useState("grid_connection");
  const [asset, setAsset] = useState("solar");
  const [question, setQuestion] = useState("");
  const [lang, setLang] = useState("zh-CN");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<ErrorResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState<null | boolean>(null);
  const [showIngestionModal, setShowIngestionModal] = useState(false);
  const [ingestionRequest, setIngestionRequest] = useState<IngestionRequest | null>(null);

  // Handle ingestion request
  const handleIngestionRequest = (errorData: ErrorResponse) => {
    const request: IngestionRequest = {
      query: question,
      province: province,
      asset_type: asset,
      doc_class: docClass,
      refusal_code: errorData.refusal_code || 'unknown',
      justification: '',
      priority: 'medium'
    };
    setIngestionRequest(request);
    setShowIngestionModal(true);
  };

  const submitIngestionRequest = async (request: IngestionRequest) => {
    try {
      const response = await fetch('/api/ingestion/request', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request)
      });

      if (response.ok) {
        alert(lang === 'zh-CN' 
          ? '补充资料请求已提交，我们会尽快处理。' 
          : 'Ingestion request submitted successfully. We will process it soon.');
        setShowIngestionModal(false);
        setIngestionRequest(null);
      } else {
        throw new Error('Failed to submit request');
      }
    } catch (err) {
      alert(lang === 'zh-CN' 
        ? '提交失败，请稍后重试。' 
        : 'Failed to submit request. Please try again later.');
    }
  };

  async function handleQuery() {
    const trimmed = question.trim();
    if (!trimmed || trimmed.length < 4) {
      alert(lang === "zh-CN" ? "请输入至少 4 个字符的问题（中文）" : "Please enter at least 4 characters");
      return;
    }

    setLoading(true);
    setError(null);
    setResponse(null);

    const traceId = `ui-${Date.now()}-${Math.random().toString(36).slice(2,8)}`;

    try {
      const res = await fetch("/api/v1/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-trace-id": traceId,
        },
        body: JSON.stringify({
          province,
          doc_class: docClass,
          asset: asset === "none" ? null : asset,
          question: trimmed,
          lang: lang === "zh-CN" ? "zh" : "en",
        }),
      });

      const data = await res.json();
      console.log("API Response Status:", res.status);
      console.log("API Response Data:", JSON.stringify(data, null, 2));

      if (res.status === 200) {
        setResponse(data);
      } else {
        setError(data);
      }
    } catch (err) {
      setError({
        error: "network_error",
        message: lang === "zh-CN" ? "网络请求失败，请稍后重试" : "Network request failed, please try again later",
        suggestion: lang === "zh-CN" ? "检查网络连接或联系技术支持" : "Check network connection or contact technical support",
        trace_id: traceId
      });
    } finally {
      setLoading(false);
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      handleQuery();
    }
  };

  useEffect(() => {
    fetch("/api/v1/health")
      .then(r => { setConnected(r.ok); return r.json(); })
      .catch(() => setConnected(false));
  }, []);

  return (
    <>
      <Head>
        <title>{lang === "zh-CN" ? "合规需求助手（试点）" : "Compliance Assistant (Pilot)"}</title>
        <meta name="description" content={lang === "zh-CN" ? "中国能源法规智能查询助手" : "Intelligent Chinese Energy Regulation Query Assistant"} />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />

      </Head>

      <div style={{
        maxWidth: 900,
        margin: "2rem auto",
        padding: "0 1rem",
        fontFamily: lang === "zh-CN" ? "'Noto Sans SC', sans-serif" : "'Inter', sans-serif",
        lineHeight: 1.6
      }}>
        {/* Connection Status */}
        <div style={{marginBottom: 8, fontSize: 12, textAlign: "center", color: "#718096"}}>
          Backend: {connected === null ? "…" : connected ? "✅ Connected" : "❌ Not connected"}
        </div>

        {/* Header */}
        <header style={{ marginBottom: "2rem", textAlign: "center" }}>
          <h1 style={{ 
            fontSize: "2rem", 
            fontWeight: 700, 
            color: "#1a365d",
            marginBottom: "0.5rem"
          }}>
            {lang === "zh-CN" ? "合规需求助手" : "Compliance Assistant"}
            <span style={{ 
              fontSize: "1rem", 
              fontWeight: 400, 
              color: "#718096",
              marginLeft: "0.5rem"
            }}>
              {lang === "zh-CN" ? "（试点）" : "(Pilot)"}
            </span>
          </h1>
          <p style={{ color: "#4a5568", fontSize: "1rem" }}>
            {lang === "zh-CN" 
              ? "基于官方文件的中国能源法规智能查询" 
              : "Intelligent Chinese Energy Regulation Queries Based on Official Documents"
            }
          </p>
          
          {/* Language Toggle */}
          <div style={{ marginTop: "1rem" }}>
            <button
              onClick={() => setLang(lang === "zh-CN" ? "en" : "zh-CN")}
              style={{
                padding: "0.5rem 1rem",
                border: "1px solid #e2e8f0",
                borderRadius: "0.375rem",
                background: "#f7fafc",
                cursor: "pointer",
                fontSize: "0.875rem"
              }}
            >
              {lang === "zh-CN" ? "English" : "中文"}
            </button>
          </div>
        </header>

        {/* Query Form */}
        <div style={{
          background: "#f7fafc",
          padding: "1.5rem",
          borderRadius: "0.5rem",
          border: "1px solid #e2e8f0",
          marginBottom: "2rem"
        }}>
          {/* Selectors */}
          <div style={{ 
            display: "grid", 
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", 
            gap: "1rem",
            marginBottom: "1rem"
          }}>
            <div>
              <label style={{ 
                display: "block", 
                fontSize: "0.875rem", 
                fontWeight: 500, 
                color: "#2d3748",
                marginBottom: "0.25rem"
              }}>
                {lang === "zh-CN" ? "省份：" : "Province:"}
              </label>
              <select 
                value={province} 
                onChange={e => setProvince(e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.5rem",
                  border: "1px solid #cbd5e0",
                  borderRadius: "0.375rem",
                  fontSize: "0.875rem"
                }}
              >
                <option value="guangdong">{lang === "zh-CN" ? "广东省" : "Guangdong"}</option>
                <option value="shandong">{lang === "zh-CN" ? "山东省" : "Shandong"}</option>
                <option value="inner_mongolia">{lang === "zh-CN" ? "内蒙古自治区" : "Inner Mongolia"}</option>
              </select>
            </div>

            <div>
              <label style={{ 
                display: "block", 
                fontSize: "0.875rem", 
                fontWeight: 500, 
                color: "#2d3748",
                marginBottom: "0.25rem"
              }}>
                {lang === "zh-CN" ? "文档类别：" : "Document Class:"}
              </label>
              <select 
                value={docClass} 
                onChange={e => setDocClass(e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.5rem",
                  border: "1px solid #cbd5e0",
                  borderRadius: "0.375rem",
                  fontSize: "0.875rem"
                }}
              >
                <option value="grid_connection">{lang === "zh-CN" ? "并网规定" : "Grid Connection"}</option>
                <option value="market_rules">{lang === "zh-CN" ? "市场规则" : "Market Rules"}</option>
                <option value="dispatch_ops">{lang === "zh-CN" ? "调度运行" : "Dispatch Operations"}</option>
              </select>
            </div>

            <div>
              <label style={{ 
                display: "block", 
                fontSize: "0.875rem", 
                fontWeight: 500, 
                color: "#2d3748",
                marginBottom: "0.25rem"
              }}>
                {lang === "zh-CN" ? "资产类型：" : "Asset Type:"}
              </label>
              <select 
                value={asset} 
                onChange={e => setAsset(e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.5rem",
                  border: "1px solid #cbd5e0",
                  borderRadius: "0.375rem",
                  fontSize: "0.875rem"
                }}
              >
                <option value="solar">{lang === "zh-CN" ? "光伏" : "Solar"}</option>
                <option value="wind">{lang === "zh-CN" ? "风电" : "Wind"}</option>
                <option value="bess">{lang === "zh-CN" ? "储能" : "Battery Storage"}</option>
                <option value="coal_flex">{lang === "zh-CN" ? "煤电灵活性" : "Coal Flexibility"}</option>
                <option value="none">{lang === "zh-CN" ? "不指定" : "Not Specified"}</option>
              </select>
            </div>
          </div>

          {/* Question Input */}
          <div>
            <label style={{ 
              display: "block", 
              fontSize: "0.875rem", 
              fontWeight: 500, 
              color: "#2d3748",
              marginBottom: "0.25rem"
            }}>
              {lang === "zh-CN" ? "问题：" : "Question:"}
            </label>
            <textarea
              placeholder={lang === "zh-CN" 
                ? "请输入您的问题（建议使用中文）\n例如：光伏电站并网需要提交哪些资料？" 
                : "Please enter your question (Chinese recommended)\nExample: What documents are required for solar grid connection?"
              }
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={handleKeyPress}
              style={{
                width: "100%",
                height: "120px",
                padding: "0.75rem",
                border: "1px solid #cbd5e0",
                borderRadius: "0.375rem",
                fontSize: "0.875rem",
                resize: "vertical",
                fontFamily: "inherit"
              }}
            />
            <div style={{ 
              fontSize: "0.75rem", 
              color: "#718096", 
              marginTop: "0.25rem" 
            }}>
              {lang === "zh-CN" 
                ? "提示：按 Ctrl+Enter 快速提交" 
                : "Tip: Press Ctrl+Enter to submit quickly"
              }
            </div>
          </div>

          {/* Submit Button */}
          <button
            onClick={handleQuery}
            disabled={loading || !question.trim()}
            style={{
              marginTop: "1rem",
              padding: "0.75rem 2rem",
              background: loading || !question.trim() ? "#a0aec0" : "#3182ce",
              color: "white",
              border: "none",
              borderRadius: "0.375rem",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: loading || !question.trim() ? "not-allowed" : "pointer",
              transition: "background-color 0.2s"
            }}
          >
            {loading 
              ? (lang === "zh-CN" ? "查询中..." : "Querying...") 
              : (lang === "zh-CN" ? "查询" : "Query")
            }
          </button>
        </div>

        {/* Results */}
        {response && (
          <div style={{
            background: "white",
            padding: "1.5rem",
            borderRadius: "0.5rem",
            border: "1px solid #e2e8f0",
            marginBottom: "2rem"
          }}>
            <div style={{ 
              display: "flex", 
              justifyContent: "space-between", 
              alignItems: "center",
              marginBottom: "1rem",
              paddingBottom: "0.5rem",
              borderBottom: "1px solid #e2e8f0"
            }}>
              <h3 style={{ 
                fontSize: "1.125rem", 
                fontWeight: 600, 
                color: "#2d3748",
                margin: 0
              }}>
                {lang === "zh-CN" ? "查询结果" : "Query Results"}
              </h3>
              <div style={{ 
                fontSize: "0.75rem", 
                color: "#718096" 
              }}>
                {lang === "zh-CN" ? "处理时间" : "Processing Time"}: {response.processing_time_ms}ms | 
                {lang === "zh-CN" ? "引用数" : "Citations"}: {response.total_citations}
              </div>
            </div>

            {/* Answer */}
            <div 
              style={{ 
                whiteSpace: "pre-wrap",
                lineHeight: 1.8,
                marginBottom: "1.5rem",
                fontSize: "0.95rem"
              }}
              dangerouslySetInnerHTML={{ __html: response.answer_zh.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }}
            />

            {/* Citations */}
            {response.citations.length > 0 && (
              <div>
                <h4 style={{ 
                  fontSize: "1rem", 
                  fontWeight: 600, 
                  color: "#2d3748",
                  marginBottom: "0.75rem"
                }}>
                  {lang === "zh-CN" ? "引用文件" : "Citations"}
                </h4>
                <ul style={{ 
                  listStyle: "none", 
                  padding: 0, 
                  margin: 0 
                }}>
                  {response.citations.map((citation, index) => (
                    <li key={index} style={{
                      padding: "0.75rem",
                      background: "#f7fafc",
                      border: "1px solid #e2e8f0",
                      borderRadius: "0.375rem",
                      marginBottom: "0.5rem",
                      fontSize: "0.875rem"
                    }}>
                      <div style={{ fontWeight: 500, color: "#2d3748" }}>
                        《{citation.title}》
                      </div>
                      <div style={{ color: "#718096", marginTop: "0.25rem" }}>
                        {lang === "zh-CN" ? "生效日期" : "Effective Date"}: {citation.effective_date}
                        {citation.url && (
                          <>
                            {" | "}
                            <a 
                              href={citation.url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              style={{ color: "#3182ce", textDecoration: "none" }}
                            >
                              {lang === "zh-CN" ? "查看原文" : "View Source"}
                            </a>
                          </>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Trace ID */}
            <div style={{ 
              fontSize: "0.75rem", 
              color: "#a0aec0", 
              marginTop: "1rem",
              textAlign: "right"
            }}>
              Trace ID: {response.trace_id}
            </div>
          </div>
        )}

        {/* Enhanced Refusal UI */}
        {error && <RefusalDisplay error={error} lang={lang} onRequestIngestion={handleIngestionRequest} />}

        {/* Ingestion Request Modal */}
        {showIngestionModal && ingestionRequest && (
          <IngestionRequestModal
            request={ingestionRequest}
            lang={lang}
            onSubmit={submitIngestionRequest}
            onClose={() => {
              setShowIngestionModal(false);
              setIngestionRequest(null);
            }}
            onUpdate={setIngestionRequest}
          />
        )}

        {/* Footer */}
        <footer style={{ 
          textAlign: "center", 
          padding: "2rem 0",
          borderTop: "1px solid #e2e8f0",
          color: "#718096",
          fontSize: "0.875rem"
        }}>
          <p>
            {lang === "zh-CN" 
              ? "本系统仅提供基于官方文件的信息查询，不构成法律建议。请以最新官方文件为准。" 
              : "This system provides information queries based on official documents only and does not constitute legal advice. Please refer to the latest official documents."
            }
          </p>
          <p style={{ marginTop: "0.5rem", fontSize: "0.75rem" }}>
            {lang === "zh-CN" 
              ? "支持省份：广东、山东、内蒙古 | 试点版本" 
              : "Supported Provinces: Guangdong, Shandong, Inner Mongolia | Pilot Version"
            }
          </p>
        </footer>
      </div>
    </>
  );
}
