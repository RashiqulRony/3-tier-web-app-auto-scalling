# Backend Target Group (Port 3000 for Node.js)
resource "aws_lb_target_group" "backend" {
  name_prefix = "bmibe-"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  
  deregistration_delay = 30
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 10
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-backend-tg"
    }
  )
  
  lifecycle {
    create_before_destroy = true
  }
}

# Backend ALB (Internal)
resource "aws_lb" "backend" {
  name_prefix        = "bmibe"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [var.backend_alb_sg_id]
  subnets            = var.private_subnet_ids
  
  enable_deletion_protection = false
  enable_http2              = true
  
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-backend-alb"
    }
  )
}

# Backend ALB Listener
resource "aws_lb_listener" "backend" {
  load_balancer_arn = aws_lb.backend.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }
  
  tags = var.tags
}

# Frontend Target Group (Port 80 for nginx)
resource "aws_lb_target_group" "frontend" {
  name_prefix = "bmife-"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  
  deregistration_delay = 30
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 10
    path                = "/"
    protocol            = "HTTP"
    matcher             = "200"
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-frontend-tg"
    }
  )
  
  lifecycle {
    create_before_destroy = true
  }
}

# Frontend ALB (Public)
resource "aws_lb" "frontend" {
  name_prefix        = "bmife-"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.frontend_alb_sg_id]
  subnets            = var.public_subnet_ids
  
  enable_deletion_protection = false
  enable_http2              = true
  
  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-frontend-alb"
    }
  )
}

# Frontend ALB Listener
resource "aws_lb_listener" "frontend" {
  load_balancer_arn = aws_lb.frontend.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
  
  tags = var.tags
}
