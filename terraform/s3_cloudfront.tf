# ---------------------------------------------------------------------------
# Private S3 bucket for the static frontend (NFR-005, AC-012).
# Never directly public; readable only by the CloudFront distribution via OAC.
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "frontend" {
  bucket_prefix = "${local.name_prefix}-frontend-"

  tags = {
    Name      = "${local.name_prefix}-frontend"
    Component = "frontend-storage"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ---------------------------------------------------------------------------
# CloudFront Origin Access Control (OAC) — signed origin requests to private S3.
# ---------------------------------------------------------------------------
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name_prefix}-oac"
  description                       = "OAC for ${local.name_prefix} frontend bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ---------------------------------------------------------------------------
# CloudFront distribution — HTTPS delivery of the static frontend via the
# generated *.cloudfront.net domain (FR-011, NFR-004, NFR-011).
# ---------------------------------------------------------------------------
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${local.name_prefix} frontend"
  default_root_object = "index.html"
  price_class         = var.cloudfront_price_class

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "s3-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-frontend"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  # SPA/static fallback so client-side routes and refreshes return index.html.
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Default CloudFront certificate; no custom domain / ACM (NFR-004).
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Component = "cdn"
  }
}

# ---------------------------------------------------------------------------
# Bucket policy: allow read only to the specific CloudFront distribution
# via the OAC service principal + SourceArn condition (least privilege).
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "frontend_bucket" {
  statement {
    sid    = "AllowCloudFrontOACRead"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.frontend.arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = data.aws_iam_policy_document.frontend_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

# ---------------------------------------------------------------------------
# Upload built frontend assets. Resolves to an empty set when the frontend
# build output is not yet present (parallel workstreams); the real assets are
# owned by the frontend workstream and uploaded from var.frontend_source_dir.
# ---------------------------------------------------------------------------
locals {
  frontend_files = fileexists("${var.frontend_source_dir}/index.html") ? fileset(var.frontend_source_dir, "**") : toset([])

  # Minimal content-type map for common static asset extensions.
  content_types = {
    html = "text/html"
    css  = "text/css"
    js   = "application/javascript"
    json = "application/json"
    svg  = "image/svg+xml"
    png  = "image/png"
    jpg  = "image/jpeg"
    jpeg = "image/jpeg"
    gif  = "image/gif"
    ico  = "image/x-icon"
    map  = "application/json"
    txt  = "text/plain"
    woff = "font/woff"
  }
}

resource "aws_s3_object" "frontend" {
  for_each = local.frontend_files

  bucket       = aws_s3_bucket.frontend.id
  key          = each.value
  source       = "${var.frontend_source_dir}/${each.value}"
  etag         = filemd5("${var.frontend_source_dir}/${each.value}")
  content_type = lookup(local.content_types, lower(element(reverse(split(".", each.value)), 0)), "application/octet-stream")
}
