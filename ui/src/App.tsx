import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Checkbox,
  Col,
  ConfigProvider,
  Empty,
  Flex,
  Input,
  Layout,
  Modal,
  Row,
  Segmented,
  Select,
  Slider,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
  theme,
} from 'antd';
import {
  AudioOutlined,
  CheckCircleOutlined,
  DownloadOutlined,
  FilterOutlined,
  GithubOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import {
  generateSound,
  getDownloadUrl,
  getPreviewUrl,
  searchSounds,
  type Facet,
  type SearchHit,
  type SearchMode,
  type SearchResponse,
} from './api';

const { Header, Content, Footer } = Layout;
const { Title, Text, Paragraph } = Typography;

const GITHUB_URL =
  import.meta.env.VITE_GITHUB_URL ?? 'https://github.com/padrisimo/eleven-typesense';
const DEFAULT_QUERY = 'explosion';
const EXAMPLES = [DEFAULT_QUERY, 'heavy metallic door', 'creaky hinge', 'footsteps on gravel'];

function facetOptions(facets: Facet[], field: string, limit = 12) {
  const facet = facets.find((item) => item.field_name === field);
  return (facet?.counts ?? [])
    .slice(0, limit)
    .map((item) => ({ label: `${item.value} · ${item.count}`, value: String(item.value) }));
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function App() {
  const { message } = AntApp.useApp();

  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [appliedQuery, setAppliedQuery] = useState(DEFAULT_QUERY);
  const [mode, setMode] = useState<SearchMode>('keyword');
  const [category, setCategory] = useState<string | undefined>();
  const [format, setFormat] = useState<string | undefined>();
  const [tags, setTags] = useState<string[]>([]);
  const [duration, setDuration] = useState<[number, number]>([0, 60]);
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const [generateOpen, setGenerateOpen] = useState(false);
  const [prompt, setPrompt] = useState('heavy metallic door slamming shut');
  const [generationDuration, setGenerationDuration] = useState(3);
  const [generating, setGenerating] = useState(false);

  const [playingId, setPlayingId] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    searchSounds({
      q: appliedQuery,
      mode,
      category,
      format,
      tags,
      min_duration: duration[0] * 1000,
      max_duration: duration[1] * 1000,
    })
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((error: unknown) => {
        if (!cancelled) message.error(errorMessage(error, 'Search failed'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [appliedQuery, mode, category, format, tags, duration, reloadKey, message]);

  useEffect(() => () => audioRef.current?.pause(), []);

  const submitSearch = () => setAppliedQuery(query.trim() || '*');

  const clearFilters = () => {
    setCategory(undefined);
    setFormat(undefined);
    setTags([]);
    setDuration([0, 60]);
  };

  const handlePreview = async (hit: SearchHit) => {
    if (playingId === hit.id && audioRef.current) {
      audioRef.current.pause();
      setPlayingId(null);
      return;
    }

    try {
      const url = await getPreviewUrl(hit.id);
      if (!audioRef.current) {
        const audio = new Audio();
        audio.onended = () => setPlayingId(null);
        audioRef.current = audio;
      }
      audioRef.current.src = url;
      await audioRef.current.play();
      setPlayingId(hit.id);
    } catch (error) {
      message.error(errorMessage(error, 'Preview unavailable'));
    }
  };

  const handleDownload = async (hit: SearchHit) => {
    try {
      const url = await getDownloadUrl(hit.id);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (error) {
      message.error(errorMessage(error, 'Download unavailable'));
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      message.warning('Write a prompt first');
      return;
    }

    setGenerating(true);
    try {
      const response = await generateSound(prompt.trim(), generationDuration);
      message.success(
        response.idempotent
          ? `Reused existing sound #${response.sound_id}`
          : `Generated sound #${response.sound_id}`,
      );
      setGenerateOpen(false);
      setQuery(prompt.trim());
      setAppliedQuery(prompt.trim());
      setReloadKey((value) => value + 1);
    } catch (error) {
      message.error(errorMessage(error, 'Generation failed'));
    } finally {
      setGenerating(false);
    }
  };

  const facets = result?.facet_counts ?? [];

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#6ee7b7',
          colorBgBase: '#0b1020',
          borderRadius: 12,
          fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
        components: {
          Card: { colorBgContainer: 'rgba(19, 27, 48, 0.78)' },
          Modal: { colorBgElevated: '#131b30' },
        },
      }}
    >
      <AntApp>
        <Layout className="app-shell">
          <Header className="app-header">
            <Flex align="center" justify="space-between">
              <Space size="small">
                <span className="logo-mark">
                  <AudioOutlined />
                </span>
                <Text strong className="brand-name">
                  Soundseek
                </Text>
              </Space>
              <Tooltip title="View the source on GitHub">
                <Button
                  type="text"
                  icon={<GithubOutlined />}
                  href={GITHUB_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="github-link"
                >
                  GitHub
                </Button>
              </Tooltip>
            </Flex>
          </Header>

          <Content className="app-content">
            <section className="hero">
              <Title level={1}>Find the sound you hear in your head.</Title>
              <Paragraph type="secondary">
                Search 200,000 sound effects, then generate a new one when the library comes up
                short.
              </Paragraph>

              <Space.Compact className="search-bar">
                <Input
                  size="large"
                  prefix={<SearchOutlined />}
                  placeholder="Try “heavy metallic door” or “creaky hinge”"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onPressEnter={submitSearch}
                  allowClear
                />
                <Button size="large" type="primary" icon={<SearchOutlined />} onClick={submitSearch}>
                  Search
                </Button>
              </Space.Compact>

              <Flex align="center" justify="space-between" wrap="wrap" gap={12} className="hero-row">
                <Segmented<SearchMode>
                  value={mode}
                  onChange={setMode}
                  options={[
                    { label: 'Keyword', value: 'keyword' },
                    { label: 'Hybrid', value: 'hybrid' },
                  ]}
                />
                <Space wrap size={[6, 6]}>
                  <Text type="secondary">Try:</Text>
                  {EXAMPLES.map((example) => (
                    <Button
                      key={example}
                      size="small"
                      type="link"
                      onClick={() => {
                        setQuery(example);
                        setAppliedQuery(example);
                      }}
                    >
                      {example}
                    </Button>
                  ))}
                </Space>
              </Flex>
            </section>

            <Row gutter={[20, 20]}>
              <Col xs={24} lg={6}>
                <Card
                  className="filter-card"
                  title={
                    <span>
                      <FilterOutlined /> Filters
                    </span>
                  }
                  extra={<Button type="link" size="small" onClick={clearFilters}>Reset</Button>}
                >
                  <Flex vertical gap={16}>
                    <div>
                      <Text className="filter-label">Category</Text>
                      <Select
                        allowClear
                        placeholder="All categories"
                        style={{ width: '100%' }}
                        value={category}
                        onChange={setCategory}
                        options={facetOptions(facets, 'category')}
                      />
                    </div>
                    <div>
                      <Text className="filter-label">Format</Text>
                      <Select
                        allowClear
                        placeholder="All formats"
                        style={{ width: '100%' }}
                        value={format}
                        onChange={setFormat}
                        options={facetOptions(facets, 'format')}
                      />
                    </div>
                    <div>
                      <Text className="filter-label">Tags</Text>
                      <Checkbox.Group
                        value={tags}
                        onChange={(values) => setTags(values.map(String))}
                        options={facetOptions(facets, 'tags', 8)}
                        className="tag-filters"
                      />
                    </div>
                    <div>
                      <Flex justify="space-between">
                        <Text className="filter-label">Duration</Text>
                        <Text type="secondary">
                          {duration[0]}s – {duration[1]}s
                        </Text>
                      </Flex>
                      <Slider
                        range
                        min={0}
                        max={60}
                        step={1}
                        value={duration}
                        onChange={(value) => setDuration(value as [number, number])}
                      />
                    </div>
                  </Flex>
                </Card>
              </Col>

              <Col xs={24} lg={18}>
                <Flex align="center" justify="space-between" wrap="wrap" gap={12} className="results-bar">
                  <Space wrap>
                    <Tag color="blue">{result?.found ?? 0} results</Tag>
                    <Tag>{result?.search_time_ms ?? 0} ms</Tag>
                    <Tag color={mode === 'hybrid' ? 'purple' : 'default'}>{mode}</Tag>
                  </Space>
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={() => setReloadKey((value) => value + 1)}
                  >
                    Refresh
                  </Button>
                </Flex>

                {result?.suggest_generate && (
                  <Alert
                    className="generate-alert"
                    type="info"
                    showIcon
                    message="Nothing good in the library?"
                    description="Describe the sound and generate a new one with AI. It becomes searchable immediately."
                    action={
                      <Button type="primary" size="small" onClick={() => setGenerateOpen(true)}>
                        Generate it
                      </Button>
                    }
                  />
                )}

                <Spin spinning={loading}>
                  {result?.hits.length ? (
                    <Row gutter={[16, 16]} className="results-grid">
                      {result.hits.map((hit) => (
                        <Col xs={24} md={12} xl={8} key={hit.id}>
                          <Card hoverable className="sound-card" styles={{ body: { padding: 16 } }}>
                            <Flex vertical gap={12} className="sound-card-body">
                              <Flex justify="space-between" align="flex-start" gap={8}>
                                <div>
                                  <Text strong className="sound-title">
                                    {hit.title}
                                  </Text>
                                  <Paragraph type="secondary" ellipsis={{ rows: 2 }} className="sound-description">
                                    {hit.description}
                                  </Paragraph>
                                </div>
                                <Tag color={hit.id > 200000 ? 'purple' : 'blue'}>#{hit.id}</Tag>
                              </Flex>

                              <Space wrap size={[6, 6]}>
                                <Tag color="cyan">{hit.category}</Tag>
                                <Tag>{hit.format.toUpperCase()}</Tag>
                                <Tag>{(hit.duration_ms / 1000).toFixed(1)}s</Tag>
                                {hit.tags.slice(0, 2).map((tag) => (
                                  <Tag key={tag}>{tag}</Tag>
                                ))}
                              </Space>

                              <Flex justify="space-between">
                                <Button
                                  size="small"
                                  type={playingId === hit.id ? 'primary' : 'default'}
                                  icon={<PlayCircleOutlined />}
                                  onClick={() => void handlePreview(hit)}
                                >
                                  {playingId === hit.id ? 'Stop' : 'Preview'}
                                </Button>
                                <Tooltip title="Simulated subscriber access">
                                  <Button
                                    size="small"
                                    icon={<DownloadOutlined />}
                                    onClick={() => void handleDownload(hit)}
                                  >
                                    Download
                                  </Button>
                                </Tooltip>
                              </Flex>
                            </Flex>
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  ) : (
                    !loading && (
                      <Card className="empty-card">
                        <Empty description="No matching sounds. Try another query or generate one." />
                      </Card>
                    )
                  )}
                </Spin>
              </Col>
            </Row>
          </Content>

          <Footer className="app-footer">
            <Space wrap split="·">
              <Text type="secondary">PostgreSQL + Typesense + ElevenLabs</Text>
              <Text type="secondary">Pinned and reproducible</Text>
              <Button
                type="link"
                size="small"
                icon={<GithubOutlined />}
                href={GITHUB_URL}
                target="_blank"
                rel="noreferrer"
              >
                Source
              </Button>
            </Space>
          </Footer>
        </Layout>

        <Modal
          title={
            <span>
              <ThunderboltOutlined /> Generate a sound
            </span>
          }
          open={generateOpen}
          onCancel={() => setGenerateOpen(false)}
          onOk={() => void handleGenerate()}
          okText={generating ? 'Generating…' : 'Generate'}
          confirmLoading={generating}
          okButtonProps={{ icon: <ThunderboltOutlined /> }}
        >
          <Flex vertical gap={16}>
            <Text type="secondary">
              The same prompt is idempotent: a second call reuses the existing sound and spends no
              credit.
            </Text>
            <Input.TextArea
              rows={3}
              value={prompt}
              maxLength={500}
              showCount
              placeholder="e.g. a heavy metallic door closing in a distant hallway"
              onChange={(event) => setPrompt(event.target.value)}
            />
            <div>
              <Flex justify="space-between">
                <Text>Duration</Text>
                <Text type="secondary">{generationDuration}s</Text>
              </Flex>
              <Slider
                min={1}
                max={30}
                value={generationDuration}
                onChange={(value) => setGenerationDuration(value as number)}
              />
            </div>
            <Alert
              type="success"
              showIcon
              icon={<CheckCircleOutlined />}
              message="Mock generator by default"
              description="Set GENERATOR=elevenlabs to use the real provider."
            />
          </Flex>
        </Modal>
      </AntApp>
    </ConfigProvider>
  );
}
