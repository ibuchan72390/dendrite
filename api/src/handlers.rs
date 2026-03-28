use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use std::process::Command;
use std::sync::Arc;

use crate::models::{AddNeuronRequest, ApiError, SearchParams};
use crate::AppState;

fn run_dendrite(db_path: &str, args: &[&str]) -> Result<serde_json::Value, String> {
    let output = Command::new("dendrite")
        .env("DENDRITE_DB", db_path)
        .args(args)
        .output()
        .map_err(|e| e.to_string())?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("dendrite error: {}", stderr));
    }

    serde_json::from_slice(&output.stdout).map_err(|e| {
        let stdout = String::from_utf8_lossy(&output.stdout);
        format!("json parse error: {} (stdout: {})", e, stdout)
    })
}

type ErrResponse = (StatusCode, Json<ApiError>);

fn err(msg: impl Into<String>) -> ErrResponse {
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(ApiError { error: msg.into() }),
    )
}

pub async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({"status": "ok"}))
}

pub async fn add_neuron(
    State(state): State<Arc<AppState>>,
    Json(body): Json<AddNeuronRequest>,
) -> Result<Json<serde_json::Value>, ErrResponse> {
    let mut args = vec!["add", "--json", &body.content];
    let title_owned;
    if let Some(ref t) = body.title {
        title_owned = t.clone();
        args.push("--title");
        args.push(&title_owned);
    }
    let result = run_dendrite(&state.db_path, &args).map_err(|e| err(e))?;
    Ok(Json(result))
}

pub async fn list_neurons(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, ErrResponse> {
    let result = run_dendrite(&state.db_path, &["list", "--json"]).map_err(|e| err(e))?;
    Ok(Json(result))
}

pub async fn get_neuron(
    State(state): State<Arc<AppState>>,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, ErrResponse> {
    let result = run_dendrite(&state.db_path, &["show", "--json", &id]).map_err(|e| err(e))?;
    Ok(Json(result))
}

pub async fn search(
    State(state): State<Arc<AppState>>,
    Query(params): Query<SearchParams>,
) -> Result<Json<serde_json::Value>, ErrResponse> {
    let top_k_str;
    let mut args = vec!["ask", "--json", &params.q];
    if let Some(k) = params.top_k {
        top_k_str = k.to_string();
        args.push("--top");
        args.push(&top_k_str);
    }
    let result = run_dendrite(&state.db_path, &args).map_err(|e| err(e))?;
    Ok(Json(result))
}

pub async fn explore(
    State(state): State<Arc<AppState>>,
    Path(concept): Path<String>,
) -> Result<Json<serde_json::Value>, ErrResponse> {
    let result =
        run_dendrite(&state.db_path, &["explore", "--json", &concept]).map_err(|e| err(e))?;
    Ok(Json(result))
}

pub async fn graph(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, ErrResponse> {
    let result = run_dendrite(&state.db_path, &["graph", "--json"]).map_err(|e| err(e))?;
    Ok(Json(result))
}

pub async fn stats(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, ErrResponse> {
    let result = run_dendrite(&state.db_path, &["stats", "--json"]).map_err(|e| err(e))?;
    Ok(Json(result))
}

pub async fn consolidate(
    State(state): State<Arc<AppState>>,
) -> Result<Json<serde_json::Value>, ErrResponse> {
    let result =
        run_dendrite(&state.db_path, &["consolidate", "--json"]).map_err(|e| err(e))?;
    Ok(Json(result))
}
