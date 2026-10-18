// All user-facing strings (Vietnamese first). Error codes map to messages here.

export const vi = {
  appTitle: "Trợ lý lớp học VSL",
  appTagline: "Nhận dạng một danh sách nhỏ ký hiệu VSL — không phải phiên dịch.",
  phaseNotice:
    "Phiên bản Giai đoạn 3 (khung thử nghiệm): nhận dạng chỉ dùng mô hình mô phỏng hoặc mẫu thử của nhà phát triển — chưa có từ vựng VSL thật.",

  nav: {
    label: "Điều hướng chính",
    communicate: "Giao tiếp",
    settings: "Cài đặt",
    privacy: "Quyền riêng tư",
    record: "Ghi mẫu",
  },

  backend: {
    heading: "Trạng thái máy chủ",
    checking: "Đang kiểm tra kết nối…",
    online: "Đã kết nối máy chủ",
    degraded: "Máy chủ hoạt động nhưng thiếu một số chức năng",
    offline: "Mất kết nối máy chủ",
    offlineHelp: "Hãy chạy: uv run python scripts/run_backend.py",
    incompatible: "Phiên bản máy chủ không khớp với ứng dụng",
  },
  connectionBanner: {
    offline:
      "Mất kết nối máy chủ. Nhận dạng ký hiệu tạm thời không dùng được — nhập chữ và đọc thành tiếng vẫn hoạt động.",
    incompatible: "Phiên bản máy chủ không khớp với ứng dụng. Hãy cập nhật cả hai rồi tải lại trang.",
  },
  components: {
    sign_model: "Nhận dạng ký hiệu",
    stt: "Giọng nói → chữ",
    tts: "Đọc thành tiếng (máy chủ)",
  },
  componentStatus: {
    ready: "Sẵn sàng",
    loading: "Đang tải",
    unavailable: "Không khả dụng",
    disabled: "Tắt",
    mock: "Mô phỏng",
  },
  mockBadge: "MOCK",
  mockBadgeLabel: "Chế độ mô phỏng: kết quả là kịch bản, không phải nhận dạng thật",

  camera: {
    heading: "Camera",
    intro:
      "Camera dùng để nhận dạng ký hiệu. Hình ảnh chỉ xử lý trên máy này, không ghi lại và không gửi đi đâu.",
    start: "Bật camera",
    stop: "Tắt camera",
    retry: "Thử lại",
    requesting: "Đang xin quyền camera…",
    requestingHint: "Hãy chọn “Cho phép” trong hộp thoại của trình duyệt.",
    active: "Camera đang bật",
    previewLabel: "Hình ảnh xem trước từ camera (lật như gương)",
    selectorLabel: "Chọn camera",
    failure: {
      denied: "Chưa cho phép camera",
      unavailable: "Không tìm thấy camera",
      in_use: "Camera đang được ứng dụng khác dùng",
      insecure: "Trình duyệt không cho phép dùng camera ở địa chỉ này",
      error: "Không mở được camera",
    },
    help: {
      denied:
        "Nhấn biểu tượng ổ khoá cạnh thanh địa chỉ → Camera → Cho phép, rồi nhấn “Thử lại”. Bạn vẫn có thể nhập chữ bên dưới.",
      unavailable: "Hãy cắm camera hoặc chọn camera khác, rồi nhấn “Thử lại”.",
      in_use: "Hãy đóng ứng dụng khác đang dùng camera (Zoom, Teams, Meet…), rồi nhấn “Thử lại”.",
      insecure: "Hãy mở ứng dụng bằng http://localhost.",
      error: "Hãy thử lại. Nếu vẫn lỗi, khởi động lại trình duyệt.",
    },
  },

  compose: {
    heading: "Nhập tin nhắn",
    label: "Tin nhắn",
    placeholder: "Nhập điều bạn muốn nói…",
    speakerLegend: "Người nói",
    send: "Gửi",
    sendAndSpeak: "Gửi và đọc",
    counter: (n: number, max: number) => `${n}/${max} ký tự`,
    enterHint: "Enter để gửi, Shift+Enter để xuống dòng.",
  },
  speakers: { student: "Học sinh", teacher: "Giáo viên" },

  transcript: {
    heading: "Hội thoại",
    empty: "Chưa có tin nhắn nào.",
    speak: "Đọc",
    speakLabel: (text: string) => `Đọc thành tiếng: ${text}`,
    spoken: "Đã đọc",
    export: "Tải hội thoại (.txt)",
    clear: "Xoá hội thoại",
    memoryNote: "Hội thoại chỉ lưu tạm trong trình duyệt và mất khi tải lại trang.",
    sources: { sign: "Ký hiệu", manual: "Nhập chữ", speech: "Giọng nói" },
  },

  tts: {
    speaking: "Đang phát",
    stop: "Dừng đọc",
    loading: "Đang tìm giọng đọc tiếng Việt…",
    unsupported: "Trình duyệt này không hỗ trợ đọc thành tiếng.",
    noVoice: "Máy này chưa có giọng đọc tiếng Việt chạy cục bộ. Tin nhắn vẫn hiển thị bằng chữ.",
    installHelp: {
      mac: "macOS: Cài đặt hệ thống → Trợ năng → Nội dung được đọc → Giọng hệ thống → Quản lý giọng → Tiếng Việt (Linh).",
      windows:
        "Windows: Cài đặt → Thời gian và ngôn ngữ → Giọng nói → Quản lý giọng nói → Thêm giọng → Tiếng Việt.",
    },
    networkWarning:
      "Giọng đọc trực tuyến gửi nội dung tin nhắn lên máy chủ của hãng trình duyệt. Chỉ bật khi bạn đồng ý.",
  },

  settings: {
    heading: "Cài đặt",
    cameraHeading: "Camera",
    noCameras: "Chưa thấy camera. Hãy bật camera một lần ở trang Giao tiếp để trình duyệt liệt kê.",
    voiceHeading: "Giọng đọc",
    voiceLabel: "Giọng đọc tiếng Việt",
    rateLabel: "Tốc độ đọc",
    test: "Nghe thử",
    testPhrase: "Xin chào, đây là giọng đọc thử.",
    allowNetwork: "Cho phép giọng đọc trực tuyến (không khuyến khích)",
    diagnosticsHeading: "Chẩn đoán",
    voicesFound: (local: number, network: number) =>
      `Giọng tiếng Việt: ${local} cục bộ, ${network} trực tuyến.`,
    voiceLocal: "cục bộ",
    voiceNetwork: "trực tuyến",
    dataHeading: "Dữ liệu trên máy này",
    deleteData: "Xoá dữ liệu cục bộ",
    deleteConfirm: "Xác nhận xoá",
    deleteCancel: "Huỷ",
    deleteExplain: "Xoá cài đặt đã lưu và hội thoại hiện tại. Không thể hoàn tác.",
    deleted: "Đã xoá dữ liệu cục bộ.",
  },

  privacy: {
    heading: "Quyền riêng tư",
    points: [
      "Hình ảnh camera chỉ xử lý trong trình duyệt trên máy này. Ứng dụng không ghi hình và không gửi hình đi đâu.",
      "Hội thoại chỉ lưu tạm trong bộ nhớ và mất khi tải lại trang. Chỉ khi bạn nhấn “Tải hội thoại” thì mới có tệp trên máy.",
      "Giọng đọc mặc định chạy cục bộ. Giọng đọc trực tuyến (gửi chữ lên mạng) bị tắt trừ khi bạn bật trong Cài đặt.",
      "Ứng dụng chỉ kết nối tới máy chủ trên chính máy này (127.0.0.1).",
      "Cài đặt (camera, giọng đọc) lưu trong trình duyệt và có thể xoá trong Cài đặt → Xoá dữ liệu cục bộ.",
      "Phiên bản thử nghiệm chỉ dành cho người lớn tham gia có đồng ý.",
    ],
  },

  recognition: {
    heading: "Nhận dạng ký hiệu",
    start: "Bắt đầu nhận dạng",
    stop: "Dừng nhận dạng",
    resume: "Tiếp tục",
    idleHint: "Ký một ký hiệu, rồi hạ tay xuống để hệ thống nhận dạng.",
    state: {
      connecting: "Đang kết nối…",
      waiting_for_hands: "Đưa tay vào khung hình",
      ready: "Sẵn sàng — hãy ký",
      signing: "Đang ký…",
      paused: "Tạm dừng vì tab bị ẩn",
      reconnecting: (n: number) => `Mất kết nối, đang thử lại (lần ${n})…`,
    },
    failure: {
      NO_CAMERA: "Hãy bật camera trước khi nhận dạng.",
      REPLAY_UNAVAILABLE: "Không tải được dữ liệu phát lại.",
      EXTRACTOR_FAILED: "Không khởi động được bộ nhận dạng điểm mốc (MediaPipe).",
      MEDIAPIPE_ASSETS_MISSING:
        "Thiếu tệp MediaPipe trên máy này. Chạy: uv run python scripts/bootstrap.py --with-models --pin, rồi tải lại trang.",
      BACKEND_UNREACHABLE: "Không kết nối được máy chủ sau nhiều lần thử.",
    } as Record<string, string>,
    failureGeneric: "Nhận dạng đã dừng do lỗi.",
    failureDetail: (detail: string) => `Chi tiết: ${detail}`,
    replayBadge: "PHÁT LẠI TỔNG HỢP",
    replayNotice:
      "Đang dùng dữ liệu phát lại tổng hợp — không phải camera và không phải ký hiệu VSL thật.",
    devModelBadge: "MÔ HÌNH THỬ NGHIỆM",
    overlayLabel: "Khung xương điểm mốc của khung hình mới nhất",
  },
  candidate: {
    confirm: "Xác nhận",
    dismiss: "Bỏ qua",
    uncertainPrompt: "Bạn muốn nói gì?",
    choose: (text: string) => `Chọn “${text}”`,
    rejected: "Không nhận ra — hãy ký lại",
    skippedHeading: "Đã bỏ qua",
    mockNoSpeech: "Chế độ mô phỏng: kết quả kịch bản không được đọc thành tiếng.",
    confidence: (p: number) => `Độ tin cậy ${Math.round(p * 100)}%`,
  },
  ladder: {
    autoSwitch: (fps: number) =>
      `Tốc độ xử lý thấp (${fps.toFixed(1)} khung/giây). Lần bắt đầu tới sẽ dùng chế độ nhẹ hơn (L2).`,
    offerL3: (fps: number) =>
      `Vẫn chậm (${fps.toFixed(1)} khung/giây). Có thể xử lý hình ảnh trên máy chủ cục bộ (127.0.0.1); hình ảnh không rời khỏi máy này và không được lưu.`,
    acceptL3: "Dùng xử lý trên máy chủ cục bộ (L3)",
    unsupported: "Máy này chưa đủ nhanh để nhận dạng ký hiệu. Hãy dùng nhập chữ.",
  },
  performance: {
    heading: "Hiệu năng (đo trên máy thật)",
    levelHeading: "Mức xử lý hình ảnh",
    levels: {
      L1: "L1 — Toàn thân trong trình duyệt (mặc định)",
      L2: "L2 — Tay và tư thế, nhẹ hơn (không có khuôn mặt)",
      L3: "L3 — Xử lý trên máy chủ cục bộ",
    },
    levelHint: "Thay đổi có hiệu lực từ lần bắt đầu nhận dạng tiếp theo.",
    fps: "Tốc độ điểm mốc",
    latency: "Độ trễ hạ tay → hiển thị (p50 / p95)",
    inference: "Thời gian suy luận",
    source: "Nguồn / chế độ",
    dropped: "Khung hình bị loại",
    heap: "Bộ nhớ JavaScript",
    backendRss: "Bộ nhớ máy chủ",
    refresh: "Làm mới",
    none: "—",
    notRunning: "Bắt đầu nhận dạng để đo.",
  },
  recorder: {
    heading: "Ghi mẫu ký hiệu (chỉ dữ liệu của chính bạn)",
    warning:
      "Chỉ ghi ký hiệu của chính bạn. Chỉ lưu điểm mốc (không có hình ảnh), giữ trong trình duyệt cho tới khi bạn tải tệp xuống.",
    glossLabel: "Mã ký hiệu (ví dụ DEV_01)",
    textLabel: "Chữ hiển thị",
    iconLabel: "Biểu tượng (từ khoá)",
    record: "Ghi một lượt (3 giây)",
    countdown: (n: number) => `Chuẩn bị… ${n}`,
    recording: "ĐANG GHI",
    takes: (n: number) => `Đã ghi ${n} lượt`,
    download: "Tải tệp ghi (.json)",
    clear: "Xoá các lượt",
    sourceFailed: "Không bắt đầu được nguồn điểm mốc.",
    needCamera: "Hãy bật camera ở trang Giao tiếp trước.",
    needLabel: "Nhập mã ký hiệu và chữ hiển thị trước khi ghi.",
  },

  errorBoundary: {
    title: "Đã xảy ra lỗi",
    body: "Ứng dụng gặp sự cố. Hãy tải lại trang.",
    reload: "Tải lại trang",
  },
} as const;

export const errorMessages: Record<string, string> = {
  VALIDATION_ERROR: "Dữ liệu gửi lên không hợp lệ.",
  PAYLOAD_TOO_LARGE: "Dữ liệu quá lớn.",
  RATE_LIMITED: "Gửi quá nhanh, vui lòng thử lại.",
  ORIGIN_FORBIDDEN: "Ứng dụng không được phép kết nối máy chủ.",
  NOT_FOUND: "Không tìm thấy.",
  PROTOCOL_MISMATCH: "Phiên bản giao thức không khớp — hãy tải lại trang.",
  FEATURE_SPEC_MISMATCH: "Cấu hình nhận dạng không khớp — hãy tải lại trang.",
  EXTRACTION_UNAVAILABLE: "Xử lý trên máy chủ không khả dụng.",
  MODEL_UNAVAILABLE: "Nhận dạng ký hiệu không khả dụng.",
  RESOURCE_EXHAUSTED: "Không đủ bộ nhớ.",
  STT_UNAVAILABLE: "Chuyển giọng nói thành chữ không khả dụng.",
  INTERNAL: "Lỗi máy chủ. Vui lòng thử lại.",
};
