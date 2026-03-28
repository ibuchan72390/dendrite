mod handlers;
mod models;

use axum::{
    routing::{get, post},
    Router,
};
use std::sync::Arc;
use tower_http::cors::CorsLayer;

#[derive(Clone)]
pub struct AppState {
    pub db_path: String,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let db_path = std::env::var("DENDRITE_DB")
        .unwrap_or_else(|_| "/data/dendrite.db".to_string());
    let port = std::env::var("PORT").unwrap_or_else(|_| "8080".to_string());

    let state = Arc::new(AppState { db_path });

    let app = Router::new()
        .route("/health", get(handlers::health))
        .route(
            "/neurons",
            post(handlers::add_neuron).get(handlers::list_neurons),
        )
        .route("/neurons/:id", get(handlers::get_neuron))
        .route("/search", get(handlers::search))
        .route("/explore/:concept", get(handlers::explore))
        .route("/graph", get(handlers::graph))
        .route("/stats", get(handlers::stats))
        .route("/consolidate", post(handlers::consolidate))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = format!("0.0.0.0:{}", port);
    tracing::info!("Listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
