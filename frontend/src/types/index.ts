// ── API Response Wrapper ──────────────────────────────────────
export interface ApiResponse<T = unknown> {
  success: boolean
  message: string
  timestamp: string
  data: T
}

// ── Auth / Session ────────────────────────────────────────────
export interface SessionInfo {
  has_session: boolean
  user_id: string | null
  cookie_count: number
  saved_at: string
  is_expired: boolean
  is_valid: boolean
  missing_cookies: string[]
}

export interface AuthStatus {
  is_running: boolean
  login_detected: boolean
  username: string | null
  is_logged_in: boolean
  profile_exists: boolean
}

// ── Comment & Sentiment ───────────────────────────────────────
export interface Comment {
  number: number
  username: string
  text: string
  comment_id: string
  like_count: number
  created_at: number
  reply_count: number
  category: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' | 'HATE_SPEECH' | 'TOXIC' | 'HUMOR'
  sentiment: string
  language: string
  is_hate_speech: boolean
  is_toxic: boolean
  is_sarcasm: boolean
  is_wellwish: boolean
  hate_score: number
  hate_words: string[]
  toxic_words: string[]
  positive_words: string[]
  negative_words: string[]
  humor_words: string[]
  emojis: string[]
  ml_confidence: number
  decision_source: string
  vader_compound: number

  // ── BARU: replies (child_comments) ──
  is_reply?: boolean
  parent_comment_id?: string
  replies?: Comment[]
  replies_fetched?: number
}

export interface RepliesSentimentBreakdown {
  positive_count: number
  negative_count: number
  neutral_count: number
  humor_count: number
  toxic_count: number
  hate_speech_count: number
  positive_percentage: number
  negative_percentage: number
  neutral_percentage: number
  humor_percentage: number
  toxic_percentage: number
  hate_percentage: number
}

export interface SentimentSummary {
  total_comments: number
  total_replies?: number
  hate_speech_count: number
  hate_percentage: number
  toxic_count: number
  toxic_percentage: number
  positive_count: number
  positive_percentage: number
  negative_count: number
  negative_percentage: number
  neutral_count: number
  neutral_percentage: number
  humor_count: number
  humor_percentage: number
  sarcasm_count: number
  sarcasm_percentage: number
  wellwish_count: number
  wellwish_percentage: number
  avg_ml_confidence: number
  top_liked: TopComment[]
  hate_examples: HateExample[]
  most_active_users: ActiveUser[]
  engagement?: EngagementSummary
  replies_sentiment_breakdown?: RepliesSentimentBreakdown
}

export interface TopComment {
  username: string
  text: string
  like_count: number
  category: string
  sentiment: string
}

export interface HateExample {
  username: string
  text: string
  hate_words: string[]
  like_count: number
}

export interface ActiveUser {
  username: string
  comment_count: number
}

// ── Post Scrape Result ────────────────────────────────────────
export interface PostResult {
  url: string
  shortcode: string
  scraped_at: string
  sentiment_mode: string
  caption: string
  likes: number
  owner_username: string
  media_id: string
  method: string
  media_type: 'PHOTO' | 'VIDEO' | 'CAROUSEL' | 'UNKNOWN'
  product_type: string
  video_views: number
  play_count: number
  shares_count: number
  reshare_count: number
  direct_send_count: number
  saves_count: number
  comments: Comment[]
  comments_count: number
  replies_count?: number          // ── BARU
  include_replies?: boolean       // ── BARU
  max_replies_per_comment?: number // ── BARU
  sentiment_summary: SentimentSummary
  _meta?: { saved_file?: string; elapsed_seconds?: number }
}

// ── Profile ───────────────────────────────────────────────────
export interface Profile {
  username: string
  full_name: string
  followers: number
  following: number
  posts_count: number
  bio: string
  is_verified: boolean
  is_private: boolean
  category: string
  profile_pic_url: string
  engagement_summary?: {
    posts_analyzed: number
    avg_likes: number
    avg_comments: number
    engagement_rate: number
  }
}

export interface EngagementSummary {
  media_type: string
  product_type: string
  likes: number
  video_views: number
  play_count: number
  shares_count: number
  reshare_count: number
  direct_send_count: number
  saves_count: number
}

// ── Output Files ──────────────────────────────────────────────
export interface OutputFile {
  name: string
  size: number
  modified: string
}

// ── Health ────────────────────────────────────────────────────
export interface HealthData {
  api: string
  engine_dir: string
  output_dir: string
  engine_files_found: boolean
}

// ── Follower / Following Item ───────────────────────────────
export interface FollowerItem {
  username: string
  full_name: string
  user_id: string
  is_verified: boolean
  is_private: boolean
  profile_pic_url: string
}

export interface FollowerListResult {
  username: string
  kind: 'followers' | 'following' | 'following_verified'
  scraped_at: string
  scraped_date: string
  success: boolean
  count: number
  items: FollowerItem[]
  total_scanned?: number
  error: string
  _meta?: { saved_file?: string; elapsed_seconds?: number }
}

export interface FollowingVerifiedResult {
  username: string
  kind: 'following_verified'
  scraped_at: string
  scraped_date: string
  success: boolean
  count: number
  total_scanned: number
  items: FollowerItem[]
  error: string
  _meta?: { saved_file?: string; elapsed_seconds?: number }
}