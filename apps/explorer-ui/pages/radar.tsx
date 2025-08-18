import { useState, useEffect } from "react";
import Head from "next/head";

interface MarketSignal {
  signal_id: string;
  title: string;
  title_en: string;
  content: string;
  content_en: string;
  signal_type: string;
  priority: string;
  province: string;
  asset_type: string;
  source_url: string;
  published_date: string;
  effective_date?: string;
  deadline_date?: string;
  tags: string[];
  impact_score: number;
  relevance_score: number;
}

interface SignalStats {
  total_signals: number;
  type_distribution: Record<string, number>;
  priority_distribution: Record<string, number>;
  province_distribution: Record<string, number>;
  asset_type_distribution: Record<string, number>;
  recent_activity: {
    count: number;
    period: string;
  };
  upcoming_deadlines: {
    count: number;
    period: string;
    signals: Array<{
      signal_id: string;
      title: string;
      deadline_date: string;
      priority: string;
    }>;
  };
}

interface FilterOptions {
  provinces: string[];
  asset_types: string[];
  signal_types: string[];
  priorities: string[];
  keywords: string;
  date_from: string;
  date_to: string;
  min_impact_score: number;
}

export default function Radar() {
  const [lang, setLang] = useState("zh-CN");
  const [signals, setSignals] = useState<MarketSignal[]>([]);
  const [stats, setStats] = useState<SignalStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterOptions>({
    provinces: [],
    asset_types: [],
    signal_types: [],
    priorities: [],
    keywords: "",
    date_from: "",
    date_to: "",
    min_impact_score: 0
  });
  const [showFilters, setShowFilters] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(20);

  // Load initial data
  useEffect(() => {
    loadSignals();
    loadStats();
  }, []);

  const loadSignals = async (page = 1) => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      
      // Add filters
      if (filters.provinces.length > 0) {
        filters.provinces.forEach(p => params.append('provinces', p));
      }
      if (filters.asset_types.length > 0) {
        filters.asset_types.forEach(a => params.append('asset_types', a));
      }
      if (filters.signal_types.length > 0) {
        filters.signal_types.forEach(s => params.append('signal_types', s));
      }
      if (filters.priorities.length > 0) {
        filters.priorities.forEach(p => params.append('priorities', p));
      }
      if (filters.keywords) {
        params.append('keywords', filters.keywords);
      }
      if (filters.date_from) {
        params.append('date_from', filters.date_from);
      }
      if (filters.date_to) {
        params.append('date_to', filters.date_to);
      }
      if (filters.min_impact_score > 0) {
        params.append('min_impact_score', filters.min_impact_score.toString());
      }
      
      // Pagination
      params.append('limit', pageSize.toString());
      params.append('offset', ((page - 1) * pageSize).toString());

      const response = await fetch(`/api/radar/signals?${params.toString()}`);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setSignals(data.signals || []);
      setTotalCount(data.total_count || 0);
      setCurrentPage(page);

    } catch (err) {
      console.error("Failed to load signals:", err);
      setError(err instanceof Error ? err.message : "Failed to load market signals");
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch('/api/radar/stats');
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  };

  const handleFilterChange = (key: keyof FilterOptions, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const applyFilters = () => {
    setCurrentPage(1);
    loadSignals(1);
  };

  const clearFilters = () => {
    setFilters({
      provinces: [],
      asset_types: [],
      signal_types: [],
      priorities: [],
      keywords: "",
      date_from: "",
      date_to: "",
      min_impact_score: 0
    });
    setCurrentPage(1);
    loadSignals(1);
  };

  const exportToCsv = async () => {
    try {
      const params = new URLSearchParams();
      
      // Add current filters
      if (filters.provinces.length > 0) {
        filters.provinces.forEach(p => params.append('provinces', p));
      }
      if (filters.asset_types.length > 0) {
        filters.asset_types.forEach(a => params.append('asset_types', a));
      }
      if (filters.signal_types.length > 0) {
        filters.signal_types.forEach(s => params.append('signal_types', s));
      }
      if (filters.priorities.length > 0) {
        filters.priorities.forEach(p => params.append('priorities', p));
      }
      if (filters.keywords) {
        params.append('keywords', filters.keywords);
      }
      if (filters.date_from) {
        params.append('date_from', filters.date_from);
      }
      if (filters.date_to) {
        params.append('date_to', filters.date_to);
      }
      if (filters.min_impact_score > 0) {
        params.append('min_impact_score', filters.min_impact_score.toString());
      }

      const response = await fetch(`/api/radar/signals/export/csv?${params.toString()}`);
      
      if (!response.ok) {
        throw new Error('Export failed');
      }

      // Download file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `market_signals_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

    } catch (err) {
      console.error("Failed to export CSV:", err);
      alert(lang === "zh-CN" ? "导出失败，请稍后重试" : "Export failed, please try again");
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return '#dc2626';
      case 'high': return '#ea580c';
      case 'medium': return '#d97706';
      case 'low': return '#65a30d';
      default: return '#6b7280';
    }
  };

  const getPriorityLabel = (priority: string) => {
    const labels = {
      'critical': { zh: '紧急', en: 'Critical' },
      'high': { zh: '高', en: 'High' },
      'medium': { zh: '中', en: 'Medium' },
      'low': { zh: '低', en: 'Low' }
    };
    return labels[priority as keyof typeof labels]?.[lang === 'zh-CN' ? 'zh' : 'en'] || priority;
  };

  const getSignalTypeLabel = (type: string) => {
    const labels = {
      'tender': { zh: '招标公告', en: 'Tender' },
      'notice': { zh: '通知公告', en: 'Notice' },
      'policy_update': { zh: '政策更新', en: 'Policy Update' },
      'market_change': { zh: '市场变化', en: 'Market Change' },
      'regulatory_change': { zh: '监管变化', en: 'Regulatory Change' }
    };
    return labels[type as keyof typeof labels]?.[lang === 'zh-CN' ? 'zh' : 'en'] || type;
  };

  const getProvinceLabel = (province: string) => {
    const labels = {
      'guangdong': { zh: '广东', en: 'Guangdong' },
      'shandong': { zh: '山东', en: 'Shandong' },
      'inner_mongolia': { zh: '内蒙古', en: 'Inner Mongolia' }
    };
    return labels[province as keyof typeof labels]?.[lang === 'zh-CN' ? 'zh' : 'en'] || province;
  };

  const getAssetTypeLabel = (assetType: string) => {
    const labels = {
      'solar': { zh: '分布式光伏', en: 'Solar PV' },
      'wind': { zh: '风电', en: 'Wind Power' },
      'battery': { zh: '储能', en: 'Battery Storage' },
      'coal_flexibility': { zh: '煤电灵活性', en: 'Coal Flexibility' }
    };
    return labels[assetType as keyof typeof labels]?.[lang === 'zh-CN' ? 'zh' : 'en'] || assetType;
  };

  const totalPages = Math.ceil(totalCount / pageSize);

  return (
    <>
      <Head>
        <title>{lang === "zh-CN" ? "市场雷达 - 地理自适应能源助手" : "Market Radar - Geo-Adaptive Energy Assistant"}</title>
        <meta name="description" content={lang === "zh-CN" ? "实时监控中国能源市场动态和监管信号" : "Real-time monitoring of Chinese energy market dynamics and regulatory signals"} />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <div style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        fontFamily: "'Noto Sans SC', 'Microsoft YaHei', sans-serif"
      }}>
        {/* Header */}
        <div style={{
          background: "rgba(255, 255, 255, 0.95)",
          backdropFilter: "blur(10px)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.2)",
          padding: "1rem 0",
          position: "sticky",
          top: 0,
          zIndex: 100
        }}>
          <div style={{
            maxWidth: "1200px",
            margin: "0 auto",
            padding: "0 1rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}>
            <div>
              <h1 style={{
                fontSize: "1.5rem",
                fontWeight: 700,
                color: "#1f2937",
                margin: 0
              }}>
                📡 {lang === "zh-CN" ? "市场雷达" : "Market Radar"}
              </h1>
              <p style={{
                fontSize: "0.875rem",
                color: "#6b7280",
                margin: "0.25rem 0 0 0"
              }}>
                {lang === "zh-CN" ? "实时监控能源市场动态" : "Real-time Energy Market Monitoring"}
              </p>
            </div>

            <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
              {/* Language Toggle */}
              <button
                onClick={() => setLang(lang === "zh-CN" ? "en" : "zh-CN")}
                style={{
                  background: "none",
                  border: "1px solid #d1d5db",
                  borderRadius: "0.375rem",
                  padding: "0.5rem 1rem",
                  fontSize: "0.875rem",
                  cursor: "pointer",
                  color: "#374151"
                }}
              >
                {lang === "zh-CN" ? "EN" : "中文"}
              </button>

              {/* Home Link */}
              <a
                href="/"
                style={{
                  color: "#3b82f6",
                  textDecoration: "none",
                  fontSize: "0.875rem",
                  fontWeight: 500
                }}
              >
                {lang === "zh-CN" ? "返回查询" : "Back to Query"}
              </a>
            </div>
          </div>
        </div>

        <div style={{
          maxWidth: "1200px",
          margin: "0 auto",
          padding: "2rem 1rem"
        }}>
          {/* Stats Dashboard */}
          {stats && (
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "1rem",
              marginBottom: "2rem"
            }}>
              <div style={{
                background: "rgba(255, 255, 255, 0.9)",
                borderRadius: "0.75rem",
                padding: "1.5rem",
                textAlign: "center",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
              }}>
                <div style={{ fontSize: "2rem", fontWeight: 700, color: "#3b82f6" }}>
                  {stats.total_signals}
                </div>
                <div style={{ fontSize: "0.875rem", color: "#6b7280", marginTop: "0.25rem" }}>
                  {lang === "zh-CN" ? "总信号数" : "Total Signals"}
                </div>
              </div>

              <div style={{
                background: "rgba(255, 255, 255, 0.9)",
                borderRadius: "0.75rem",
                padding: "1.5rem",
                textAlign: "center",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
              }}>
                <div style={{ fontSize: "2rem", fontWeight: 700, color: "#10b981" }}>
                  {stats.recent_activity.count}
                </div>
                <div style={{ fontSize: "0.875rem", color: "#6b7280", marginTop: "0.25rem" }}>
                  {lang === "zh-CN" ? "近期活动" : "Recent Activity"}
                </div>
              </div>

              <div style={{
                background: "rgba(255, 255, 255, 0.9)",
                borderRadius: "0.75rem",
                padding: "1.5rem",
                textAlign: "center",
                boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
              }}>
                <div style={{ fontSize: "2rem", fontWeight: 700, color: "#f59e0b" }}>
                  {stats.upcoming_deadlines.count}
                </div>
                <div style={{ fontSize: "0.875rem", color: "#6b7280", marginTop: "0.25rem" }}>
                  {lang === "zh-CN" ? "即将截止" : "Upcoming Deadlines"}
                </div>
              </div>
            </div>
          )}

          {/* Controls */}
          <div style={{
            background: "rgba(255, 255, 255, 0.9)",
            borderRadius: "0.75rem",
            padding: "1.5rem",
            marginBottom: "2rem",
            boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
          }}>
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "1rem"
            }}>
              <h2 style={{
                fontSize: "1.125rem",
                fontWeight: 600,
                color: "#1f2937",
                margin: 0
              }}>
                {lang === "zh-CN" ? "筛选和导出" : "Filter and Export"}
              </h2>

              <div style={{ display: "flex", gap: "0.75rem" }}>
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  style={{
                    background: showFilters ? "#3b82f6" : "transparent",
                    color: showFilters ? "white" : "#3b82f6",
                    border: "1px solid #3b82f6",
                    borderRadius: "0.375rem",
                    padding: "0.5rem 1rem",
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    cursor: "pointer"
                  }}
                >
                  🔍 {lang === "zh-CN" ? "筛选" : "Filter"}
                </button>

                <button
                  onClick={exportToCsv}
                  style={{
                    background: "#10b981",
                    color: "white",
                    border: "none",
                    borderRadius: "0.375rem",
                    padding: "0.5rem 1rem",
                    fontSize: "0.875rem",
                    fontWeight: 500,
                    cursor: "pointer"
                  }}
                >
                  📊 {lang === "zh-CN" ? "导出CSV" : "Export CSV"}
                </button>
              </div>
            </div>

            {/* Filter Panel */}
            {showFilters && (
              <div style={{
                background: "#f9fafb",
                borderRadius: "0.5rem",
                padding: "1rem",
                border: "1px solid #e5e7eb"
              }}>
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                  gap: "1rem",
                  marginBottom: "1rem"
                }}>
                  {/* Keywords */}
                  <div>
                    <label style={{
                      display: "block",
                      fontSize: "0.875rem",
                      fontWeight: 500,
                      color: "#374151",
                      marginBottom: "0.5rem"
                    }}>
                      {lang === "zh-CN" ? "关键词" : "Keywords"}
                    </label>
                    <input
                      type="text"
                      value={filters.keywords}
                      onChange={(e) => handleFilterChange('keywords', e.target.value)}
                      placeholder={lang === "zh-CN" ? "搜索关键词..." : "Search keywords..."}
                      style={{
                        width: "100%",
                        padding: "0.5rem",
                        border: "1px solid #d1d5db",
                        borderRadius: "0.375rem",
                        fontSize: "0.875rem"
                      }}
                    />
                  </div>

                  {/* Date From */}
                  <div>
                    <label style={{
                      display: "block",
                      fontSize: "0.875rem",
                      fontWeight: 500,
                      color: "#374151",
                      marginBottom: "0.5rem"
                    }}>
                      {lang === "zh-CN" ? "开始日期" : "From Date"}
                    </label>
                    <input
                      type="date"
                      value={filters.date_from}
                      onChange={(e) => handleFilterChange('date_from', e.target.value)}
                      style={{
                        width: "100%",
                        padding: "0.5rem",
                        border: "1px solid #d1d5db",
                        borderRadius: "0.375rem",
                        fontSize: "0.875rem"
                      }}
                    />
                  </div>

                  {/* Date To */}
                  <div>
                    <label style={{
                      display: "block",
                      fontSize: "0.875rem",
                      fontWeight: 500,
                      color: "#374151",
                      marginBottom: "0.5rem"
                    }}>
                      {lang === "zh-CN" ? "结束日期" : "To Date"}
                    </label>
                    <input
                      type="date"
                      value={filters.date_to}
                      onChange={(e) => handleFilterChange('date_to', e.target.value)}
                      style={{
                        width: "100%",
                        padding: "0.5rem",
                        border: "1px solid #d1d5db",
                        borderRadius: "0.375rem",
                        fontSize: "0.875rem"
                      }}
                    />
                  </div>

                  {/* Impact Score */}
                  <div>
                    <label style={{
                      display: "block",
                      fontSize: "0.875rem",
                      fontWeight: 500,
                      color: "#374151",
                      marginBottom: "0.5rem"
                    }}>
                      {lang === "zh-CN" ? "最低影响分数" : "Min Impact Score"} ({filters.min_impact_score.toFixed(1)})
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={filters.min_impact_score}
                      onChange={(e) => handleFilterChange('min_impact_score', parseFloat(e.target.value))}
                      style={{
                        width: "100%"
                      }}
                    />
                  </div>
                </div>

                <div style={{
                  display: "flex",
                  gap: "0.75rem",
                  justifyContent: "flex-end"
                }}>
                  <button
                    onClick={clearFilters}
                    style={{
                      background: "transparent",
                      color: "#6b7280",
                      border: "1px solid #d1d5db",
                      borderRadius: "0.375rem",
                      padding: "0.5rem 1rem",
                      fontSize: "0.875rem",
                      cursor: "pointer"
                    }}
                  >
                    {lang === "zh-CN" ? "清除" : "Clear"}
                  </button>
                  <button
                    onClick={applyFilters}
                    style={{
                      background: "#3b82f6",
                      color: "white",
                      border: "none",
                      borderRadius: "0.375rem",
                      padding: "0.5rem 1rem",
                      fontSize: "0.875rem",
                      fontWeight: 500,
                      cursor: "pointer"
                    }}
                  >
                    {lang === "zh-CN" ? "应用筛选" : "Apply Filters"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Results */}
          <div style={{
            background: "rgba(255, 255, 255, 0.9)",
            borderRadius: "0.75rem",
            padding: "1.5rem",
            boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
          }}>
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "1.5rem"
            }}>
              <h2 style={{
                fontSize: "1.125rem",
                fontWeight: 600,
                color: "#1f2937",
                margin: 0
              }}>
                {lang === "zh-CN" ? "市场信号" : "Market Signals"} ({totalCount})
              </h2>

              {/* Pagination Info */}
              {totalPages > 1 && (
                <div style={{
                  fontSize: "0.875rem",
                  color: "#6b7280"
                }}>
                  {lang === "zh-CN" ? "第" : "Page"} {currentPage} {lang === "zh-CN" ? "页，共" : "of"} {totalPages} {lang === "zh-CN" ? "页" : "pages"}
                </div>
              )}
            </div>

            {/* Loading */}
            {loading && (
              <div style={{
                textAlign: "center",
                padding: "3rem",
                color: "#6b7280"
              }}>
                {lang === "zh-CN" ? "加载中..." : "Loading..."}
              </div>
            )}

            {/* Error */}
            {error && (
              <div style={{
                background: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: "0.5rem",
                padding: "1rem",
                color: "#dc2626",
                marginBottom: "1rem"
              }}>
                {error}
              </div>
            )}

            {/* Signals List */}
            {!loading && !error && signals.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                {signals.map((signal) => (
                  <div
                    key={signal.signal_id}
                    style={{
                      border: "1px solid #e5e7eb",
                      borderRadius: "0.5rem",
                      padding: "1.5rem",
                      background: "white"
                    }}
                  >
                    {/* Signal Header */}
                    <div style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      marginBottom: "1rem"
                    }}>
                      <div style={{ flex: 1 }}>
                        <h3 style={{
                          fontSize: "1.125rem",
                          fontWeight: 600,
                          color: "#1f2937",
                          margin: "0 0 0.5rem 0",
                          lineHeight: "1.4"
                        }}>
                          {lang === "zh-CN" ? signal.title : signal.title_en}
                        </h3>

                        <div style={{
                          display: "flex",
                          flexWrap: "wrap",
                          gap: "0.75rem",
                          fontSize: "0.75rem",
                          color: "#6b7280"
                        }}>
                          <span style={{
                            background: getPriorityColor(signal.priority),
                            color: "white",
                            padding: "0.25rem 0.5rem",
                            borderRadius: "0.25rem",
                            fontWeight: 500
                          }}>
                            {getPriorityLabel(signal.priority)}
                          </span>

                          <span style={{
                            background: "#f3f4f6",
                            color: "#374151",
                            padding: "0.25rem 0.5rem",
                            borderRadius: "0.25rem"
                          }}>
                            {getSignalTypeLabel(signal.signal_type)}
                          </span>

                          <span>📍 {getProvinceLabel(signal.province)}</span>
                          <span>⚡ {getAssetTypeLabel(signal.asset_type)}</span>
                          <span>📅 {signal.published_date}</span>
                          
                          {signal.deadline_date && (
                            <span style={{ color: "#dc2626", fontWeight: 500 }}>
                              ⏰ {lang === "zh-CN" ? "截止" : "Deadline"}: {signal.deadline_date}
                            </span>
                          )}
                        </div>
                      </div>

                      <div style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "flex-end",
                        gap: "0.25rem",
                        marginLeft: "1rem"
                      }}>
                        <div style={{
                          fontSize: "0.75rem",
                          color: "#6b7280"
                        }}>
                          {lang === "zh-CN" ? "影响分数" : "Impact"}: {(signal.impact_score * 100).toFixed(0)}%
                        </div>
                        <div style={{
                          fontSize: "0.75rem",
                          color: "#6b7280"
                        }}>
                          {lang === "zh-CN" ? "相关度" : "Relevance"}: {(signal.relevance_score * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>

                    {/* Signal Content */}
                    <div style={{
                      fontSize: "0.875rem",
                      lineHeight: "1.6",
                      color: "#374151",
                      marginBottom: "1rem"
                    }}>
                      {lang === "zh-CN" ? signal.content : signal.content_en}
                    </div>

                    {/* Tags and Source */}
                    <div style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      paddingTop: "1rem",
                      borderTop: "1px solid #f3f4f6"
                    }}>
                      <div style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "0.5rem"
                      }}>
                        {signal.tags.slice(0, 5).map((tag, index) => (
                          <span
                            key={index}
                            style={{
                              background: "#eff6ff",
                              color: "#1d4ed8",
                              padding: "0.25rem 0.5rem",
                              borderRadius: "0.25rem",
                              fontSize: "0.75rem"
                            }}
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>

                      <a
                        href={signal.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          color: "#3b82f6",
                          textDecoration: "none",
                          fontSize: "0.875rem",
                          fontWeight: 500
                        }}
                      >
                        {lang === "zh-CN" ? "查看原文" : "View Source"} →
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* No Results */}
            {!loading && !error && signals.length === 0 && (
              <div style={{
                textAlign: "center",
                padding: "3rem",
                color: "#6b7280"
              }}>
                <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>📡</div>
                <div style={{ fontSize: "1.125rem", fontWeight: 500, marginBottom: "0.5rem" }}>
                  {lang === "zh-CN" ? "暂无市场信号" : "No Market Signals"}
                </div>
                <div style={{ fontSize: "0.875rem" }}>
                  {lang === "zh-CN" ? "请尝试调整筛选条件" : "Try adjusting your filters"}
                </div>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gap: "0.5rem",
                marginTop: "2rem",
                paddingTop: "1rem",
                borderTop: "1px solid #e5e7eb"
              }}>
                <button
                  onClick={() => loadSignals(currentPage - 1)}
                  disabled={currentPage <= 1}
                  style={{
                    padding: "0.5rem 1rem",
                    border: "1px solid #d1d5db",
                    borderRadius: "0.375rem",
                    background: currentPage <= 1 ? "#f9fafb" : "white",
                    color: currentPage <= 1 ? "#9ca3af" : "#374151",
                    cursor: currentPage <= 1 ? "not-allowed" : "pointer",
                    fontSize: "0.875rem"
                  }}
                >
                  {lang === "zh-CN" ? "上一页" : "Previous"}
                </button>

                <span style={{
                  padding: "0.5rem 1rem",
                  fontSize: "0.875rem",
                  color: "#6b7280"
                }}>
                  {currentPage} / {totalPages}
                </span>

                <button
                  onClick={() => loadSignals(currentPage + 1)}
                  disabled={currentPage >= totalPages}
                  style={{
                    padding: "0.5rem 1rem",
                    border: "1px solid #d1d5db",
                    borderRadius: "0.375rem",
                    background: currentPage >= totalPages ? "#f9fafb" : "white",
                    color: currentPage >= totalPages ? "#9ca3af" : "#374151",
                    cursor: currentPage >= totalPages ? "not-allowed" : "pointer",
                    fontSize: "0.875rem"
                  }}
                >
                  {lang === "zh-CN" ? "下一页" : "Next"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}