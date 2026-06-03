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

  // replies (child_comments)
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
  replies_count?: number
  include_replies?: boolean
  max_replies_per_comment?: number
  sentiment_summary: SentimentSummary
  _meta?: { saved_file?: string; elapsed_seconds?: number }
}

// ── Unified Scrape Result ─────────────────────────────────────
export interface UnifiedResult extends PostResult {
  /** Data likers (hanya ada kalau scrape_likers=true) */
  likers: LikerItem[]
  likers_fetched: number
  likes_count: number
  likers_method: string
  likers_error: string | null
  /** Aggressive mode flag */
  aggressive_likers?: boolean
}

/** Request ke endpoint /api/scrape/unified */
export interface ScrapeUnifiedRequest {
  url: string
  max_comments: number
  include_replies: boolean
  max_replies_per_comment: number
  scrape_likers: boolean
  max_likers: number
  aggressive_likers: boolean
  checkpoint_size: number
  checkpoint_delay_min: number
  checkpoint_delay_max: number
  page_delay_min: number
  page_delay_max: number
}

// ── Likers ────────────────────────────────────────────────────
export interface LikerItem {
  user_id: string
  username: string
  full_name: string
  is_verified: boolean
  is_private: boolean
  profile_pic_url: string
}

export interface LikersResult {
  url: string
  shortcode: string
  scraped_at: string
  media_id: string
  owner_username: string
  /** Total likes di post (angka dari IG) */
  likes_count: number
  /** Berapa liker yang berhasil diambil */
  likers_fetched: number
  /** rest | graphql */
  method: string
  likers: LikerItem[]
  error: string | null
  _meta?: { saved_file?: string; elapsed_seconds?: number }
}

/** Request ke endpoint /api/scrape/post/likers */
export interface ScrapeLikersRequest {
  url: string
  max_likers?: number           // 0 = semua
  checkpoint_size?: number      // default 200
  checkpoint_delay_min?: number // detik
  checkpoint_delay_max?: number // detik
  page_delay_min?: number
  page_delay_max?: number
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

// ── Mutual Follow Analysis ────────────────────────────────────
export interface MutualFollowItem extends FollowerItem {
  follows_back: true
}

export interface MutualFollowAnalysis {
  target_username: string
  scraped_at: string
  followers_count: number
  following_count: number
  mutual_count: number
  mutuals: MutualFollowItem[]
  not_following_back: FollowerItem[]
  not_followed_back: FollowerItem[]
}

// ── Profile Post Item ─────────────────────────────────────────
export interface PostComment {
  username: string
  text: string
  comment_id: string
  like_count: number
  created_at: number
  reply_count: number
  replies: Array<{
    username: string
    text: string
    comment_id: string
    like_count: number
    created_at: number
    parent_comment_id: string
  }>
}

export interface ProfilePost {
  media_id: string
  shortcode: string
  url: string
  media_type: 'PHOTO' | 'VIDEO' | 'CAROUSEL'
  product_type: string
  taken_at: number
  taken_at_iso: string
  caption: string
  like_count: number
  comment_count: number
  view_count: number
  play_count: number
  thumbnail_url: string
  is_video: boolean
  location: string
  comments: PostComment[]
  comments_fetched: number
}

export interface ProfilePostsResult {
  username: string
  date_from: string | null
  date_to: string | null
  scraped_at: string
  scraped_date: string
  success: boolean
  total_posts: number
  posts: ProfilePost[]
  error: string
  _meta?: { saved_file?: string; elapsed_seconds?: number }
}

export interface ScrapeProfilePostsRequest {
  username: string
  date_from?: string
  date_to?: string
  max_posts?: number
  include_comments?: boolean
  max_comments_per_post?: number
  max_replies_per_comment?: number
}