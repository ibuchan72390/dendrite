use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct AddNeuronRequest {
    pub content: String,
    pub title: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ApiError {
    pub error: String,
}

#[derive(Debug, Deserialize)]
pub struct SearchParams {
    pub q: String,
    pub top_k: Option<u8>,
}
