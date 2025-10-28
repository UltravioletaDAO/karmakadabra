//! HTTP endpoints implemented by the x402 **facilitator**.
//!
//! These are the server-side handlers for processing client-submitted x402 payments.
//! They include both protocol-critical endpoints (`/verify`, `/settle`) and discovery endpoints (`/supported`, etc).
//!
//! All payloads follow the types defined in the `x402-rs` crate, and are compatible
//! with the TypeScript and Go client SDKs.
//!
//! Each endpoint consumes or produces structured JSON payloads defined in `x402-rs`,
//! and is compatible with official x402 client SDKs.

use axum::extract::State;
use axum::http::{StatusCode, header};
use axum::response::Response;
use axum::{Json, response::IntoResponse};
use serde_json::json;
use tracing::instrument;

use crate::chain::FacilitatorLocalError;
use crate::facilitator::Facilitator;
use crate::facilitator_local::FacilitatorLocal;
use crate::types::{
    ErrorResponse, FacilitatorErrorReason, MixedAddress, SettleRequest, VerifyRequest,
    VerifyResponse,
};

/// `GET /verify`: Returns a machine-readable description of the `/verify` endpoint.
///
/// This is served by the facilitator to help clients understand how to construct
/// a valid [`VerifyRequest`] for payment verification.
///
/// This is optional metadata and primarily useful for discoverability and debugging tools.
#[instrument(skip_all)]
pub async fn get_verify_info() -> impl IntoResponse {
    Json(json!({
        "endpoint": "/verify",
        "description": "POST to verify x402 payments",
        "body": {
            "paymentPayload": "PaymentPayload",
            "paymentRequirements": "PaymentRequirements",
        }
    }))
}

/// `GET /settle`: Returns a machine-readable description of the `/settle` endpoint.
///
/// This is served by the facilitator to describe the structure of a valid
/// [`SettleRequest`] used to initiate on-chain payment settlement.
#[instrument(skip_all)]
pub async fn get_settle_info() -> impl IntoResponse {
    Json(json!({
        "endpoint": "/settle",
        "description": "POST to settle x402 payments",
        "body": {
            "paymentPayload": "PaymentPayload",
            "paymentRequirements": "PaymentRequirements",
        }
    }))
}

/// `GET /supported`: Lists the x402 payment schemes and networks supported by this facilitator.
///
/// Facilitators may expose this to help clients dynamically configure their payment requests
/// based on available network and scheme support.
#[instrument(skip_all)]
pub async fn get_supported(State(facilitator): State<FacilitatorLocal>) -> impl IntoResponse {
    let kinds = facilitator.kinds();
    (
        StatusCode::OK,
        Json(json!({
            "kinds": kinds,
        })),
    )
}

pub async fn get_health(State(facilitator): State<FacilitatorLocal>) -> impl IntoResponse {
    let health = facilitator.health();
    (
        StatusCode::OK,
        Json(json!({
            "providers": health,
        })),
    )
}

/// `GET /`: Serves the landing page HTML for the facilitator.
///
/// This is a bilingual (English/Spanish) landing page that explains
/// the x402 protocol and available endpoints.
#[instrument(skip_all)]
pub async fn get_index() -> impl IntoResponse {
    let html = include_str!("../static/index.html");
    (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "text/html; charset=utf-8")],
        html
    )
}

/// `GET /logo.png`: Serves the Ultravioleta DAO logo.
///
/// The logo is embedded in the binary at compile time.
/// To customize: replace static/logo.png before building.
#[instrument(skip_all)]
pub async fn get_logo() -> impl IntoResponse {
    let logo = include_bytes!("../static/logo.png");
    (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "image/png")],
        logo.as_ref()
    )
}

/// `GET /favicon.ico`: Serves the favicon for the facilitator landing page.
///
/// The favicon is embedded in the binary at compile time.
/// To customize: replace static/favicon.ico before building.
#[instrument(skip_all)]
pub async fn get_favicon() -> impl IntoResponse {
    let favicon = include_bytes!("../static/favicon.ico");
    (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "image/x-icon")],
        favicon.as_ref()
    )
}

/// `POST /verify`: Facilitator-side verification of a proposed x402 payment.
///
/// This endpoint checks whether a given payment payload satisfies the declared
/// [`PaymentRequirements`], including signature validity, scheme match, and fund sufficiency.
///
/// Responds with a [`VerifyResponse`] indicating whether the payment can be accepted.
#[instrument(skip_all)]
pub async fn post_verify(
    State(facilitator): State<FacilitatorLocal>,
    Json(body): Json<VerifyRequest>,
) -> impl IntoResponse {
    match facilitator.verify(&body).await {
        Ok(valid_response) => (StatusCode::OK, Json(valid_response)).into_response(),
        Err(error) => {
            tracing::warn!(
                error = ?error,
                body = %serde_json::to_string(&body).unwrap_or_else(|_| "<can-not-serialize>".to_string()),
                "Verification failed"
            );
            error.into_response()
        }
    }
}

/// `POST /settle`: Facilitator-side execution of a valid x402 payment on-chain.
///
/// Given a valid [`SettleRequest`], this endpoint attempts to execute the payment
/// via ERC-3009 `transferWithAuthorization`, and returns a [`SettleResponse`] with transaction details.
///
/// This endpoint is typically called after a successful `/verify` step.
#[instrument(skip_all)]
pub async fn post_settle(
    State(facilitator): State<FacilitatorLocal>,
    Json(body): Json<SettleRequest>,
) -> impl IntoResponse {
    match facilitator.settle(&body).await {
        Ok(valid_response) => (StatusCode::OK, Json(valid_response)).into_response(),
        Err(error) => {
            tracing::warn!(
                error = ?error,
                body = %serde_json::to_string(&body).unwrap_or_else(|_| "<can-not-serialize>".to_string()),
                "Settlement failed"
            );
            error.into_response()
        }
    }
}

fn invalid_schema(payer: Option<MixedAddress>) -> VerifyResponse {
    VerifyResponse::invalid(payer, FacilitatorErrorReason::InvalidScheme)
}

impl IntoResponse for FacilitatorLocalError {
    fn into_response(self) -> Response {
        let error = self;

        let bad_request = (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse {
                error: "Invalid request".to_string(),
            }),
        )
            .into_response();

        match error {
            FacilitatorLocalError::SchemeMismatch(payer, ..) => {
                (StatusCode::OK, Json(invalid_schema(payer))).into_response()
            }
            FacilitatorLocalError::ReceiverMismatch(payer, ..)
            | FacilitatorLocalError::InvalidSignature(payer, ..)
            | FacilitatorLocalError::InvalidTiming(payer, ..)
            | FacilitatorLocalError::InsufficientValue(payer) => {
                (StatusCode::OK, Json(invalid_schema(Some(payer)))).into_response()
            }
            FacilitatorLocalError::NetworkMismatch(payer, ..)
            | FacilitatorLocalError::UnsupportedNetwork(payer) => (
                StatusCode::OK,
                Json(VerifyResponse::invalid(
                    payer,
                    FacilitatorErrorReason::InvalidNetwork,
                )),
            )
                .into_response(),
            FacilitatorLocalError::ContractCall(..)
            | FacilitatorLocalError::InvalidAddress(..)
            | FacilitatorLocalError::ClockError(_) => bad_request,
            FacilitatorLocalError::DecodingError(reason) => (
                StatusCode::OK,
                Json(VerifyResponse::invalid(
                    None,
                    FacilitatorErrorReason::FreeForm(reason),
                )),
            )
                .into_response(),
            FacilitatorLocalError::InsufficientFunds(payer) => (
                StatusCode::OK,
                Json(VerifyResponse::invalid(
                    Some(payer),
                    FacilitatorErrorReason::InsufficientFunds,
                )),
            )
                .into_response(),
        }
    }
}
